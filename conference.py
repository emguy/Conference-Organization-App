#!/usr/bin/env python

import logging
import json
import os
import time
import httplib

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from google.appengine.api import memcache
from google.appengine.api import taskqueue

from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import TeeShirtSize
from models import Session
from models import SessionForm
from models import SessionForms
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import BooleanMessage
from models import ConflictException
from models import StringMessage
from models import SessionType

from datetime import datetime, time
from settings import WEB_CLIENT_ID
from  utils import getUserId

# default values for create conference objects
# it is only been used in _createConferenceObject()
DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

# default values for create session objects
# it is only been used in _createSessionObject()
SESSION_DEFAULTS = {
    "duration": 60,
    "typeOfSession": ["NOT_SPECIFIED"],
}

# query operators
OPERATORS = {
            "EQ":   "=",
            "GT":   ">",
            "GTEQ": ">=",
            "LT":   "<",
            "LTEQ": "<=",
            "NE":   "!="
            }

# query fields
FIELDS =    {
            "CITY": "city",
            "TOPIC": "topics",
            "MONTH": "month",
            "MAX_ATTENDEES": "maxAttendees",
            }

# here are some container for passing request arguments
CONF_GET_REQUEST = endpoints.ResourceContainer(
  message_types.VoidMessage,
  websafeConferenceKey=messages.StringField(1),
)
CONF_POST_REQUEST = endpoints.ResourceContainer(
  ConferenceForm,
  websafeConferenceKey=messages.StringField(1),
)
SESSION_GET_REQUEST = endpoints.ResourceContainer(
  message_types.VoidMessage,
  websafeConferenceKey = messages.StringField(1),
)
SESSION_POST_REQUEST = endpoints.ResourceContainer(
  SessionForm,
  websafeConferenceKey = messages.StringField(1),
)
SPEAKER_GET_REQUEST = endpoints.ResourceContainer(
  message_types.VoidMessage,
  speaker = messages.StringField(1),
)

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID

# the key name used by _cacheAnnouncement() in the memcahe
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"

# helper class --- needed for conference registration
class BooleanMessage(messages.Message):
  """BooleanMessage -- outbound Boolean value message"""
  data = messages.BooleanField(1)

# helper class --- needed for conference registration
class ConflictException(endpoints.ServiceException):
  """ConflictException -- exception mapped to HTTP 409 response"""
  http_status = httplib.CONFLICT

# main class starts from here
@endpoints.api( name="conference",
                version="v1",
                allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID],
                scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
  """Conference API v0.1"""

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#
#       Session objects
#
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  def _copySessionToForm(self, session):
    """Copy relevant fields from Session to SessionForm.
       Set the speakerName using the second passed argument.
    """
    sf = SessionForm()
    date = getattr(session, "date")
    startTime = getattr(session, "startTime")
    endTime = getattr(session, "endTime")
    duration = (endTime.hour * 60 + endTime.minute) \
              - (startTime.hour * 60 + startTime.minute) 
    setattr(sf, "name", getattr(session, "name"))
    setattr(sf, "highlights", getattr(session, "highlights"))
    setattr(sf, "typeOfSession", getattr(SessionType, getattr(session, "typeOfSession")))
    setattr(sf, "speaker", getattr(session, "speaker"))
    setattr(sf, "date", str(date))
    setattr(sf, "startTime", str(startTime))
    setattr(sf, "duration", duration)
    sf.check_initialized()
    return sf

  def _createSessionObject(self, request):
    """Create a new Session object, returning SessionForm/request."""
    # make sure that the user is authed
    user = endpoints.get_current_user()
    if not user:
      raise endpoints.UnauthorizedException("Authorization required")
    user_id = getUserId(user, id_type="oauth")
    # check if conf exists given websafeConfKey
    wsck = request.websafeConferenceKey
    conf = ndb.Key(urlsafe=wsck).get()
    # check that conference exists
    if not conf:
      raise endpoints.NotFoundException(
        "No conference found with key: %s" % request.websafeConferenceKey)
    # check if the user is the organizer of the conference
    if user_id != conf.organizerUserId:
      raise endpoints.ForbiddenException(
        "Only the owner can update the conference.")
    # check wether the "name" field is filled by user
    if not request.name:
      raise endpoints.BadRequestException("Session 'name' field required")
    # copy SessionForm/ProtoRPC Message into dict
    data = {field.name: getattr(request, field.name) for field in request.all_fields()}
    #-------------------------------------------------
    # data["speaker"] = user_id # this is for testing
    #-------------------------------------------------
    # add default values for those missing (both data model & outbound Message)
    for df in SESSION_DEFAULTS:
      if data[df] in (None, []):
        data[df] = DEFAULTS[df]
        setattr(request, df, DEFAULTS[df])
    # convert sessionType from enum to string
    if data["typeOfSession"]: 
      data["typeOfSession"] = str(data["typeOfSession"])
    # convert date from strings to Date objects
    if data["date"]: # date
      data["date"] = datetime.strptime(data["date"][:10], "%Y-%m-%d").date()
      # check if the date is during the conference period
      conf_start_date = getattr(conf, "startDate")
      conf_end_date = getattr(conf, "endDate")
      if data["date"] < conf_start_date or data["date"] > conf_end_date:
        raise endpoints.BadRequestException("Invallid date")
    # convert time from strings to time objects
    if data["startTime"]: # time
      data["startTime"] = datetime.strptime(data["startTime"][:8], "%H:%M:%S").time()
    # compute the endTime using the duration field
    if data["duration"] and data["startTime"]: 
      endTime_minute = (data["startTime"].minute + data["duration"]) % 60
      endTime_hour = data["startTime"].hour \
                + (data["startTime"].minute + data["duration"]) / 60
      data["endTime"] = time(endTime_hour, endTime_minute)
    # delete unused fields
    del[data["duration"]]
    del[data["websafeConferenceKey"]]
    # make conference Key from the websafe conference key
    c_key = ndb.Key(urlsafe=wsck)
    # allocate new Session ID with the conference key as parent
    s_id = Session.allocate_ids(size=1, parent=c_key)[0]
    # make Session key from ID
    s_key = ndb.Key(Session, s_id, parent=c_key)
    data["key"] = s_key
    # creates the Session object and put onto the cloud datastore
    Session(**data).put() 
    # return the original Session Form
    return self._copySessionToForm(s_key.get())

  def _createSessionObject(self, request):
    """Create a new Session object, returning SessionForm/request."""
    # make sure that the user is authed
    user = endpoints.get_current_user()
    if not user:
      raise endpoints.UnauthorizedException("Authorization required")
    user_id = getUserId(user, id_type="oauth")

    # check if conf exists given websafeConfKey
    wsck = request.websafeConferenceKey
    conf = ndb.Key(urlsafe=wsck).get()
    # check that conference exists
    if not conf:
      raise endpoints.NotFoundException(
        "No conference found with key: %s" % request.websafeConferenceKey)

  #----------------------------------------------------------
  # API: create a conference session (open only to the conference organizer)
  #----------------------------------------------------------
  @endpoints.method(SESSION_POST_REQUEST, SessionForm,
          path="conference/{websafeConferenceKey}/new_session",
          http_method="PUT", name="createSession")
  def createSession(self, request):
    """create session w/provided fields & return the info."""
    return self._createSessionObject(request)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#
#       session queries
#
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

  #----------------------------------------------------------
  # API: query all sessions in a conference itendified by the websafeConferenceKey
  #----------------------------------------------------------
  @endpoints.method(SESSION_GET_REQUEST, SessionForms,
          path="conference/{websafeConferenceKey}/all_sessions",
          http_method="POST", name="getAllSessions")
  def getAllSessions(self, request):
    """Return all sessions in the speicified conference."""
    # check if conf exists given websafeConfKey
    c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
    conf = c_key.get()
    # check that conference exists
    if not conf:
      raise endpoints.NotFoundException(
        "No conference found with key: %s" % request.websafeConferenceKey)
    # create ancestor query for this conference
    sessions = Session.query(ancestor=c_key)
    # return set of SessionForm objects per Session
    return SessionForms(
      items=[self._copySessionToForm(session) for session in sessions]
    )

  #----------------------------------------------------------
  # API: query all sessions by the speaker (requires the user id)
  #----------------------------------------------------------
  @endpoints.method(SPEAKER_GET_REQUEST, SessionForms,
          path="speaker/{speaker}",
          http_method="POST", name="getSessionsBySpeaker")
  def getSessionsBySpeaker(self, request):
    """Return all sessions presented by a specified speaker."""
    # get raw results
    query_result = Session.query()
    # apply the filter using the speaker's id
    query_result = query_result.filter(Session.speaker == request.speaker)
    # we then do some ordering using date and time
    query_result = query_result.order(Session.date)
    query_result = query_result.order(Session.startTime)
    # return the resultant query result
    return SessionForms(
      items=[self._copySessionToForm(session) for session in query_result]
    )

  #----------------------------------------------------------
  # API: query all sessions by a given topic in a conference 
  #----------------------------------------------------------
  @endpoints.method(SESSION_GET_REQUEST, SessionForms,
          path="conference/{websafeConferenceKey}/{topic}",
          http_method="POST", name="getSessionsBySpeaker")
  def getSessionsBySpeaker(self, request):
    """Return all sessions presented by a specified speaker."""
    # get raw results
    query_result = Session.query()
    # apply the filter using the speaker's id
    query_result = query_result.filter(Session.speaker == request.speaker)
    # we then do some ordering using date and time
    query_result = query_result.order(Session.date)
    query_result = query_result.order(Session.startTime)
    # return the resultant query result
    return SessionForms(
      items=[self._copySessionToForm(session) for session in query_result]
    )

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#
#       Profile objects 
#
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  def _copyProfileToForm(self, prof):
    """Copy relevant fields from Profile to ProfileForm."""
    # copy relevant fields from Profile to ProfileForm
    pf = ProfileForm()
    for field in pf.all_fields():
      if hasattr(prof, field.name):
        # convert t-shirt string to Enum; just copy others
        if field.name == "teeShirtSize":
          setattr(pf, field.name, getattr(TeeShirtSize, getattr(prof, field.name)))
        else:
          setattr(pf, field.name, getattr(prof, field.name))
    pf.check_initialized()
    return pf

  def _getProfileFromUser(self):
    """Return user Profile from datastore, creating new one if non-existent."""
    # make usre that the user is authed
    user = endpoints.get_current_user()
    if not user:
      raise endpoints.UnauthorizedException("Authorization required")
    # get Profile from database
    user_id = getUserId(user, id_type="oauth")
    p_key = ndb.Key(Profile, user_id)
    profile = p_key.get() # this creates a profile object
    # create new Profile if not there
    if not profile:
      profile = Profile(
             key = p_key,
             displayName = user.nickname(), 
             mainEmail= user.email(),
             teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
      )
      profile.put() # this place the profile object on google cloud datastore
    return profile  # return Profile

  def _doProfile(self, save_request=None):
    """Get user Profile and return to user, possibly updating it first."""
    # get user Profile
    prof = self._getProfileFromUser()
    # if saveProfile(), process user-modifyable fields
    if save_request:
      for field in ("displayName", "teeShirtSize"):
        if hasattr(save_request, field):
          val = getattr(save_request, field)
          if val:
            setattr(prof, field, str(val))
    # save it to the google cloud
    prof.put()
    # return ProfileForm
    return self._copyProfileToForm(prof)

  #----------------------------------------------------------
  # API: retrive the user profile form
  #----------------------------------------------------------
  @endpoints.method(message_types.VoidMessage, ProfileForm,
          path="profile", http_method="GET", name="getProfile")
  def getProfile(self, request):
    """Return user profile."""
    return self._doProfile()

  #----------------------------------------------------------
  # API: save/update and return the user profile (and the form)
  #----------------------------------------------------------
  @endpoints.method(ProfileMiniForm, ProfileForm, path="profile", 
            http_method="POST", name="saveProfile")
  def saveProfile(self, request):
    """Update & return user profile."""
    return self._doProfile(request)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#
#       Conference objects
#
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  def _copyConferenceToForm(self, conf, displayName):
    """Copy relevant fields from Conference to ConferenceForm.
       Set the origanizer using the displayName.
    """
    cf = ConferenceForm()
    for field in cf.all_fields():
      if hasattr(conf, field.name):
        # convert Date to date string; just copy others
        if field.name.endswith("Date"):
          setattr(cf, field.name, str(getattr(conf, field.name)))
        else:
          setattr(cf, field.name, getattr(conf, field.name))
      elif field.name == "websafeKey":
        setattr(cf, field.name, conf.key.urlsafe())
    if displayName:
      setattr(cf, "organizerDisplayName", displayName)
    cf.check_initialized()
    return cf

  def _createConferenceObject(self, request):
    """Create or update Conference object, returning ConferenceForm/request."""
    # make sure user is authed
    user = endpoints.get_current_user()
    if not user:
      raise endpoints.UnauthorizedException("Authorization required")
    user_id = getUserId(user, id_type="oauth")
    # check wether the 'name' field is filled by user
    if not request.name:
      raise endpoints.BadRequestException("Conference 'name' field required")
    # copy ConferenceForm/ProtoRPC Message into dict
    data = {field.name: getattr(request, field.name) for field in request.all_fields()}
    del data["websafeKey"]
    del data["organizerDisplayName"]
    # add default values for those missing (both data model & outbound Message)
    for df in DEFAULTS:
      if data[df] in (None, []):
        data[df] = DEFAULTS[df]
        setattr(request, df, DEFAULTS[df])
    # convert dates from strings to Date objects; set month based on start_date
    if data["startDate"]: # start date
      data["startDate"] = datetime.strptime(data["startDate"][:10], "%Y-%m-%d").date()
      data["month"] = data["startDate"].month
    else:
      data["month"] = 0
    if data["endDate"]: # end date
      data["endDate"] = datetime.strptime(data["endDate"][:10], "%Y-%m-%d").date()
    # set seatsAvailable to be same as maxAttendees on creation
    # both for data model & outbound Message
    if data["maxAttendees"] > 0:
      data["seatsAvailable"] = data["maxAttendees"]
      setattr(request, "seatsAvailable", data["maxAttendees"])
    # make Profile Key from user ID
    p_key = ndb.Key(Profile, user_id)
    # allocate new Conference ID with Profile key as parent
    c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
    # make Conference key from ID
    c_key = ndb.Key(Conference, c_id, parent=p_key)
    data["key"] = c_key
    data["organizerUserId"] = request.organizerUserId = user_id
    # creates the conference object and put onto the cloud datastore
    Conference(**data).put() 
    # send confirmation email 
    taskqueue.add(params={"email": user.email(),
        "conferenceInfo": repr(request)},
        url="/tasks/send_confirmation_email"
    )
    # return the (updated) ConferenceForm
    return request

  #----------------------------------------------------------
  # API: create conferences and return the forms
  #----------------------------------------------------------
  @endpoints.method(ConferenceForm, ConferenceForm, path="conference",
          http_method="POST", name="createConference")
  def createConference(self, request):
    """Create new conference."""
    return self._createConferenceObject(request)

  #----------------------------------------------------------
  # API: get user's conferences
  #----------------------------------------------------------
  @endpoints.method(message_types.VoidMessage, ConferenceForms,
          path="conferences/attending",
          http_method="GET", name="getConferencesToAttend")
  def getConferencesToAttend(self, request):
    """Get list of conferences that user has registered for."""
    # get user Profile
    prof = self._getProfileFromUser()
    # get conferenceKeysToAttend from profile.
    conf_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend]
    conferences = ndb.get_multi(conf_keys)
    # get organizers
    organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences]
    profiles = ndb.get_multi(organisers)
    # put display names in a dict for easier fetching
    names = {}
    for profile in profiles:
        names[profile.key.id()] = profile.displayName
    # return set of ConferenceForm objects per Conference
    return ConferenceForms(items=[self._copyConferenceToForm(conf, names[conf.organizerUserId])\
     for conf in conferences]
    )

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#
#       Conference queries
#
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    @ndb.transactional()
    def _updateConferenceObject(self, request):
      # make sure the user is authed
      user = endpoints.get_current_user()
      if not user:
        raise endpoints.UnauthorizedException("Authorization required")
      user_id = getUserId(user, id_type="oauth")
      # copy ConferenceForm/ProtoRPC Message into dict
      data = {field.name: getattr(request, field.name) for field in request.all_fields()}
      # update existing conference
      conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
      # check that conference exists
      if not conf:
        raise endpoints.NotFoundException(
          "No conference found with key: %s" % request.websafeConferenceKey)
      # check that the user is owner
      if user_id != conf.organizerUserId:
        raise endpoints.ForbiddenException(
          "Only the owner can update the conference.")
      # Not getting all the fields, so don't create a new object; just
      # copy relevant fields from ConferenceForm to Conference object
      for field in request.all_fields():
        data = getattr(request, field.name)
        # only copy fields where we get data
        if data not in (None, []):
          # special handling for dates (convert string to Date)
          if field.name in ("startDate", "endDate"):
            data = datetime.strptime(data, "%Y-%m-%d").date()
            if field.name == "startDate":
              conf.month = data.month
          # write to Conference object
          setattr(conf, field.name, data)
      conf.put()
      prof = ndb.Key(Profile, user_id).get()
      # return the conference form
      return self._copyConferenceToForm(conf, getattr(prof, "displayName"))

  def _getQuery(self, request):
    """Return formatted query from the submitted filters."""
    q = Conference.query() # get all
    inequality_filter, filters = self._formatFilters(request.filters)
    # If exists, sort on inequality filter first
    if not inequality_filter:
      q = q.order(Conference.name)
    else:
      q = q.order(ndb.GenericProperty(inequality_filter))
      q = q.order(Conference.name)
    # apply filters
    for filtr in filters:
      if filtr["field"] in ["month", "maxAttendees"]:
        filtr["value"] = int(filtr["value"]) # cast into integers
      formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
      q = q.filter(formatted_query) # apply filters
    return q

  def _formatFilters(self, filters):
    """Parse, check validity and format user supplied filters."""
    formatted_filters = [] 
    inequality_field = None 
    for f in filters:
      filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}
      try:
        filtr["field"] = FIELDS[filtr["field"]] # value translation
        filtr["operator"] = OPERATORS[filtr["operator"]] # value translation
      except KeyError:
        raise endpoints.BadRequestException("Filter contains invalid field or operator.")
      # Every operation except "=" is an inequality
      if filtr["operator"] != "=":
        # check if inequality operation has been used in previous filters
        # disallow the filter if inequality was performed on a different field before
        # track the field on which the inequality operation is performed
        if inequality_field and inequality_field != filtr["field"]:
          raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
        else:
          inequality_field = filtr["field"]
      formatted_filters.append(filtr)
    return (inequality_field, formatted_filters)

  #----------------------------------------------------------
  # API: update conferences and return the forms
  #----------------------------------------------------------
  @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
          path="conference/{websafeConferenceKey}",
          http_method="PUT", name="updateConference")
  def updateConference(self, request):
    """Update conference w/provided fields & return w/updated info."""
    return self._updateConferenceObject(request)

  #----------------------------------------------------------
  # API: query conferences
  #----------------------------------------------------------
  @endpoints.method(ConferenceQueryForms, ConferenceForms,
          path="queryConferences", http_method="POST",
          name="queryConferences")
  def queryConferences(self, request):
    conferences = self._getQuery(request)
    # need to fetch organiser displayName from profiles
    # get all keys and use get_multi for speed
    organisers = [(ndb.Key(Profile, conf.organizerUserId)) for conf in conferences]
    profiles = ndb.get_multi(organisers)

    # put display names in a dict for easier fetching
    names = {}
    for profile in profiles:
      names[profile.key.id()] = profile.displayName

    return ConferenceForms(
            items=[self._copyConferenceToForm(conf, names[conf.organizerUserId]) for conf in \
            conferences]
    )

  #----------------------------------------------------------
  # API: Return requested conference (by websafeConferenceKey).
  #----------------------------------------------------------
  @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
          path="conference/{websafeConferenceKey}",
          http_method="GET", name="getConference")
  def getConference(self, request):
    """Return requested conference (by websafeConferenceKey)."""
    # get Conference object from request; bail if not found
    conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
    if not conf:
      raise endpoints.NotFoundException(
        "No conference found with key: %s" % request.websafeConferenceKey)
    prof = conf.key.parent().get()
    # return ConferenceForm
    return self._copyConferenceToForm(conf, getattr(prof, "displayName"))

  #----------------------------------------------------------
  # API: query conferences by the organizer
  #----------------------------------------------------------
  @endpoints.method(message_types.VoidMessage, ConferenceForms,
          path="getConferencesCreated",
          http_method="POST", name="getConferencesCreated")
  def getConferencesCreated(self, request):
    """Return conferences created by user."""
    # make sure user is authed
    user = endpoints.get_current_user()
    if not user:
      raise endpoints.UnauthorizedException("Authorization required")
    # create the profile key
    p_key = ndb.Key(Profile, getUserId(user, id_type="oauth"))
    # create ancestor query for this user
    conferences = Conference.query(ancestor=p_key)
    # get the user profile and display name
    prof = p_key.get()
    displayName = getattr(prof, "displayName")
    # return set of ConferenceForm objects per Conference
    return ConferenceForms(
      items=[self._copyConferenceToForm(conf, displayName) for conf in conferences]
    )

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#
#       Registration 
#
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  @ndb.transactional(xg=True) # enable multiple entity groups with different ancestors
  def _conferenceRegistration(self, request, reg=True):
    """Register or unregister user for selected conference."""
    retval = None
    prof = self._getProfileFromUser() # get user Profile

    # check if conf exists given websafeConfKey
    # get conference; check that it exists
    wsck = request.websafeConferenceKey
    conf = ndb.Key(urlsafe=wsck).get()
    if not conf:
      raise endpoints.NotFoundException(
        'No conference found with key: %s' % wsck)
    # register
    if reg:
      # check if user already registered otherwise add
      if wsck in prof.conferenceKeysToAttend:
        raise ConflictException(
          "You have already registered for this conference")
      # check if seats avail
      if conf.seatsAvailable <= 0:
        raise ConflictException(
          "There are no seats available.")
      # register user, take away one seat
      prof.conferenceKeysToAttend.append(wsck)
      conf.seatsAvailable -= 1
      retval = True
    # unregister
    else:
      # check if user already registered
      if wsck in prof.conferenceKeysToAttend:
        # unregister user, add back one seat
        prof.conferenceKeysToAttend.remove(wsck)
        conf.seatsAvailable += 1
        retval = True
      else:
        retval = False
    # write things back to the datastore & return
    prof.put()
    conf.put()
    return BooleanMessage(data=retval)

  # register user for selected conference
  @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
          path="conference/{websafeConferenceKey}",
          http_method="POST", name="registerForConference")
  def registerForConference(self, request):
    """Register user for selected conference."""
    return self._conferenceRegistration(request)

  # unregister user for selected conference
  @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
          path='conference/{websafeConferenceKey}',
          http_method='DELETE', name='unregisterFromConference')
  def unregisterFromConference(self, request):
    """Unregister user for selected conference."""
    return self._conferenceRegistration(request, reg=False)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#
#       Announcements 
#
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
  @staticmethod
  def _cacheAnnouncement():
    """Create Announcement & assign to memcache; used by
    memcache cron job & putAnnouncement().
    """
    confs = Conference.query(ndb.AND(
      Conference.seatsAvailable <= 5,
      Conference.seatsAvailable > 0)
    ).fetch(projection=[Conference.name])

    if confs:
      # If there are almost sold out conferences,
      # format announcement and set it in memcache
      announcement = "%s %s" % (
        "Last chance to attend! The following conferences "
        "are nearly sold out:",
        ", ".join(conf.name for conf in confs))
      memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
    else:
      # If there are no sold out conferences,
      # delete the memcache announcements entry
      announcement = ""
      memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

    return announcement

  #----------------------------------------------------------
  # API: Return Announcement from memcache.
  #----------------------------------------------------------
  @endpoints.method(message_types.VoidMessage, StringMessage,
          path="conference/announcement/get",
          http_method="GET", name="getAnnouncement")
  def getAnnouncement(self, request):
    """Return Announcement from memcache."""
    announcement = memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY)
    if not announcement:
        announcement = ""
    return StringMessage(data=announcement)

# registers API
api = endpoints.api_server([ConferenceApi]) 
