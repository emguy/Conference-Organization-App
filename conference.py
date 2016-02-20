#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""
__author__ = "wesc+api@google.com (Wesley Chun)"

import logging
from datetime import datetime
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

from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import TeeShirtSize
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import BooleanMessage
from models import ConflictException
from models import StringMessage

from settings import WEB_CLIENT_ID
from  utils import getUserId

from google.appengine.api import memcache

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

FIELDS =    {
            'CITY': 'city',
            'TOPIC': 'topics',
            'MONTH': 'month',
            'MAX_ATTENDEES': 'maxAttendees',
            }

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID

# needed for conference registration
class BooleanMessage(messages.Message):
  """BooleanMessage -- outbound Boolean value message"""
  data = messages.BooleanField(1)

class ConflictException(endpoints.ServiceException):
  """ConflictException -- exception mapped to HTTP 409 response"""
  http_status = httplib.CONFLICT

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

@endpoints.api( name="conference",
                version="v1",
                allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID],
                scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
  """Conference API v0.1"""
# - - - Profile objects - - - - - - - - - - - - - - - - - - -
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
    return profile      # return Profile

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
    # 
    prof.put()
    # return ProfileForm
    return self._copyProfileToForm(prof)

# - - - Conference objects - - - - - - - - - - - - - - - - -
  def _copyConferenceToForm(self, conf, displayName):
    """Copy relevant fields from Conference to ConferenceForm."""
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
    # preload necessary data items
    user = endpoints.get_current_user()
    if not user:
      raise endpoints.UnauthorizedException("Authorization required")
    user_id = getUserId(user)

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
    if data["startDate"]:
      data["startDate"] = datetime.strptime(data["startDate"][:10], "%Y-%m-%d").date()
      data["month"] = data["startDate"].month
    else:
      data["month"] = 0
    if data["endDate"]:
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

    # create Conference & return (modified) ConferenceForm
    Conference(**data).put()

    return request

  def _getQuery(self, request):
    """Return formatted query from the submitted filters."""
    q = Conference.query()
    inequality_filter, filters = self._formatFilters(request.filters)

    # If exists, sort on inequality filter first
    if not inequality_filter:
      q = q.order(Conference.name)
    else:
      q = q.order(ndb.GenericProperty(inequality_filter))
      q = q.order(Conference.name)

    for filtr in filters:
      if filtr["field"] in ["month", "maxAttendees"]:
        filtr["value"] = int(filtr["value"])
      formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
      q = q.filter(formatted_query)
    return q

  def _formatFilters(self, filters):
    """Parse, check validity and format user supplied filters."""
    formatted_filters = []
    inequality_field = None
    for f in filters:
      filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}
      try:
        filtr["field"] = FIELDS[filtr["field"]]
        filtr["operator"] = OPERATORS[filtr["operator"]]
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


# - - - Registration - - - - - - - - - - - - - - - - - - - -
  @ndb.transactional(xg=True)
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

# - - - Announcements - - - - - - - - - - - - - - - - - - - -

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
      announcement = '%s %s' % (
        'Last chance to attend! The following conferences '
        'are nearly sold out:',
        ', '.join(conf.name for conf in confs))
      memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
    else:
      # If there are no sold out conferences,
      # delete the memcache announcements entry
      announcement = ""
      memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

    return announcement


















  # handle profiles
  @endpoints.method(message_types.VoidMessage, ProfileForm,
          path="profile", http_method="GET", name="getProfile")
  def getProfile(self, request):
    """Return user profile."""
    return self._doProfile()

  @endpoints.method(ProfileMiniForm, ProfileForm, path="profile", 
            http_method="POST", name="saveProfile")
  def saveProfile(self, request):
    """Update & return user profile."""
    return self._doProfile(request)

  # create conferences
  @endpoints.method(ConferenceForm, ConferenceForm, path="conference",
          http_method="POST", name="createConference")
  def createConference(self, request):
    """Create new conference."""
    return self._createConferenceObject(request)

  # query conferences 1
  @endpoints.method(ConferenceQueryForms, ConferenceForms,
              path="queryConferences", http_method="POST",
              name="queryConferences")
  def queryConferences(self, request):
    """Query for conferences."""
    conferences = self._getQuery(request)
    # return individual ConferenceForm object per Conference
    return ConferenceForms(
      items=[self._copyConferenceToForm(conf, "") for conf in conferences]
    )

  # query conferences 2
  @endpoints.method(message_types.VoidMessage, ConferenceForms,
          path="getConferencesCreated",
          http_method="POST", name="getConferencesCreated")
  def getConferencesCreated(self, request):
    """Return conferences created by user."""
    # make sure user is authed
    user = endpoints.get_current_user()
    if not user:
      raise endpoints.UnauthorizedException("Authorization required")
    # make profile key
    p_key = ndb.Key(Profile, getUserId(user, id_type="oauth"))
    # create ancestor query for this user
    conferences = Conference.query(ancestor=p_key)
    conferences = Conference.query()
    # get the user profile and display name
    prof = p_key.get()
    displayName = getattr(prof, "displayName")
    # return set of ConferenceForm objects per Conference
    return ConferenceForms(
      items=[self._copyConferenceToForm(conf, displayName) for conf in conferences]
    )

  # conference registration
  @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
          path='conference/{websafeConferenceKey}',
          http_method='POST', name='registerForConference')
  def registerForConference(self, request):
    """Register user for selected conference."""
    return self._conferenceRegistration(request)

  # get user's conferences
  @endpoints.method(message_types.VoidMessage, ConferenceForms,
          path='conferences/attending',
          http_method='GET', name='getConferencesToAttend')
  def getConferencesToAttend(self, request):
    """Get list of conferences that user has registered for."""
    # get user Profile
    prof = self._getProfileFromUser()
    # get conferenceKeysToAttend from profile.
    conf_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend]
    conferences = ndb.get_multi(conf_keys)
    # return set of ConferenceForm objects per Conference
    return ConferenceForms(items=[self._copyConferenceToForm(conf, "")\
     for conf in conferences]
    )

  @endpoints.method(message_types.VoidMessage, ConferenceForms,
          path='filterPlayground',
          http_method='GET', name='filterPlayground')
  def filterPlayground(self, request):
    q = Conference.query()
    # simple filter usage:
    # q = q.filter(Conference.city == "Paris")
  
    # advanced filter building and usage
    # field = "city"
    # operator = "="
    # value = "London"
    # f = ndb.query.FilterNode(field, operator, value)
    # q = q.filter(f)
  
    # TODO
    # add 2 filters:
    # 1: city equals to London
    q = q.filter(Conference.city == "London")
    # 2: topic equals "Medical Innovations"
    q = q.filter(Conference.topics == "Medical Innovations")
    # 3: order by conference name
    q = q.order(Conference.name)
    # 4: filter for june
    q = q.filter(Conference.maxAttendees > 10)
  
    return ConferenceForms(
      items=[self._copyConferenceToForm(conf, "") for conf in q]
    )



  @endpoints.method(message_types.VoidMessage, StringMessage,
          path='conference/announcement/get',
          http_method='GET', name='getAnnouncement')
  def getAnnouncement(self, request):
    """Return Announcement from memcache."""
    # TODO 1
    # return an existing announcement from Memcache or an empty string.
    announcement = memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY)
    announcement = ""
    return StringMessage(data=announcement)

# registers API
api = endpoints.api_server([ConferenceApi]) 
