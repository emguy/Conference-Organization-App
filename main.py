#!/usr/bin/env python
import webapp2
from google.appengine.api import app_identity
from google.appengine.api import mail
from conference import ConferenceApi

class setFeatureSpeakerHandler(webapp2.RequestHandler)
  """ Set/update the feature speaker of a conference in Memcache. """
  def post(self):
    wsck = self.request.get("websafeConferenceKey")
    ConferenceApi._cacheFeaturedSpeaker(wsck)
    self.response.set_status(204)

class SetAnnouncementHandler(webapp2.RequestHandler):
  def get(self):
    """ Set Announcement in Memcache. """
    ConferenceApi._cacheAnnouncement()
    self.response.set_status(204)

class SendConfirmationEmailHandler(webapp2.RequestHandler):
  def post(self):
    """ Send email confirming Conference creation. """
    mail.send_mail(
      "noreply@%s.appspotmail.com" % (
          app_identity.get_application_id()),     
      self.request.get("email"),                 
      "You created a new Conference!",          
      "Hi, you have created a following "      
      "conference:\r\n\r\n%s" % self.request.get("conferenceInfo")
    )

app = webapp2.WSGIApplication([
  ("/crons/set_announcement", SetAnnouncementHandler),
  ("/tasks/set_feature_speaker", setFeatureSpeakerHandler),
  ("/tasks/send_confirmation_email", SendConfirmationEmailHandler),
], debug=True)
