#!/usr/bin/env python

""" models.py

Udacity conference server-side Python App Engine data & ProtoRPC models

"""

import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb

class Session(ndb.Model):
  """Session -- conference session info"""
  name            = ndb.StringProperty(required=True)
  highlights      = ndb.StringProperty()
  speaker         = ndb.StringProperty()
  typeOfSession   = ndb.StringProperty(default="NOT_SPECIFIED")
  date            = ndb.DateProperty()
  startTime       = ndb.TimeProperty()
  endTime         = ndb.TimeProperty()

class SessionForm(messages.Message):
  """SessionForm -- Session outbound form message"""
  name            = messages.StringField(1)
  highlights      = messages.StringField(2)
  speaker         = messages.StringField(3)
  duration        = messages.IntegerField(4, variant=messages.Variant.INT32)
  typeOfSession   = messages.EnumField("SessionType", 5)
  date            = messages.StringField(6)
  startTime       = messages.StringField(7)

class SessionForms(messages.Message):
  """SessionForms -- multiple Session outbound form message"""
  items = messages.MessageField(SessionForm, 1, repeated=True)

class SessionType(messages.Enum):
  """SessionType -- session type enumeration value"""
  NOT_SPECIFIED = 0
  PAPER = 1
  PANEL = 2
  POSTER = 3
  WORKSHOP = 4
  LECURE = 5
  KEYNOTE = 6

class ConflictException(endpoints.ServiceException):
  """ConflictException -- exception mapped to HTTP 409 response"""
  http_status = httplib.CONFLICT

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)

class BooleanMessage(messages.Message):
  """BooleanMessage-- outbound Boolean value message"""
  data = messages.BooleanField(1)

class Profile(ndb.Model):
  """Profile -- User profile object"""
  displayName = ndb.StringProperty()
  mainEmail = ndb.StringProperty()
  teeShirtSize = ndb.StringProperty(default="NOT_SPECIFIED")
  conferenceKeysToAttend = ndb.StringProperty(repeated=True)

class ProfileMiniForm(messages.Message):
  """ProfileMiniForm -- update Profile form message"""
  displayName = messages.StringField(1)
  teeShirtSize = messages.EnumField("TeeShirtSize", 2)

class ProfileForm(messages.Message):
  """ProfileForm -- Profile outbound form message"""
  userId = messages.StringField(1)
  displayName = messages.StringField(2)
  mainEmail = messages.StringField(3)
  teeShirtSize = messages.EnumField("TeeShirtSize", 4)

class TeeShirtSize(messages.Enum):
  """TeeShirtSize -- t-shirt size enumeration value"""
  NOT_SPECIFIED = 1
  XS_M = 2
  XS_W = 3
  S_M = 4
  S_W = 5
  M_M = 6
  M_W = 7
  L_M = 8
  L_W = 9
  XL_M = 10
  XL_W = 11
  XXL_M = 12
  XXL_W = 13
  XXXL_M = 14
  XXXL_W = 15

class Conference(ndb.Model):
  """Conference -- Conference object"""
  name            = ndb.StringProperty(required=True)
  description     = ndb.StringProperty()
  organizerUserId = ndb.StringProperty()
  topics          = ndb.StringProperty(repeated=True)
  city            = ndb.StringProperty()
  startDate       = ndb.DateProperty()
  month           = ndb.IntegerProperty()
  endDate         = ndb.DateProperty()
  maxAttendees    = ndb.IntegerProperty()
  seatsAvailable  = ndb.IntegerProperty()

class ConferenceForm(messages.Message):
  """ConferenceForm -- Conference outbound form message"""
  name            = messages.StringField(1)
  description     = messages.StringField(2)
  organizerUserId = messages.StringField(3)
  topics          = messages.StringField(4, repeated=True)
  city            = messages.StringField(5)
  startDate       = messages.StringField(6)
  month           = messages.IntegerField(7, variant=messages.Variant.INT32)
  maxAttendees    = messages.IntegerField(8, variant=messages.Variant.INT32)
  seatsAvailable  = messages.IntegerField(9, variant=messages.Variant.INT32)
  endDate         = messages.StringField(10)
  websafeKey      = messages.StringField(11)
  organizerDisplayName = messages.StringField(12)

class ConferenceForms(messages.Message):
  """ConferenceForms -- multiple Conference outbound form message"""
  items = messages.MessageField(ConferenceForm, 1, repeated=True)

class ConferenceQueryForm(messages.Message):
  """ConferenceQueryForm -- Conference query inbound form message"""
  field = messages.StringField(1)
  operator = messages.StringField(2)
  value = messages.StringField(3)

class ConferenceQueryForms(messages.Message):
  """ConferenceQueryForms -- multiple ConferenceQueryForm inbound form message"""
  filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)

