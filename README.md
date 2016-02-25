# Conference-Organization-App

Written in Python, this is a cloud-based API server to provide functionalities
to organize conferences events with massive amount of participants.  All user
data are stored in the Google's cloud datastore (NoSQL).  I extended the
functionality of this application to support conference sessions, users's
wishlists, time issue resolution, and to allow users to return required
searches for sessions and registered conferences. The web frontend and the
android frontend has been provided by Udacity.

This web application is deployed on the Google's Cloud Platform:
https://emguy-122217.appspot.com

## APIs
You can test the API server at [here][1].

## Requirements
1. [Python 2.7][2]
2. [Google App Engine SDK for Python][]

## Setup Instructions
1. In the file `app.yaml`, change the field `application` using the app ID you have created from the Google's developer console.
2. Download the JSON client file generated for your app ID from Google's developer console.
3. At the top of `settings.py`, update the field `WEB_CLIENT_ID` using the one generated for you app ID by Google's developer console.
4. Do the same for the file `static/js/app.js` for the field `CLIENT_ID`.
5. To run the app on the local server (by default http://localhost:8080), execute `dev_appserver.py APP_DIR`.
6. You can also use Google App Engine to deploy this application onto the google cloud.

## Session Design Choices
In the file `models.py`, the class `Session` is defined as

```Python
class Session(ndb.Model):
  """Session -- conference session info"""
  name            = ndb.StringProperty(required=True)
  highlights      = ndb.StringProperty()
  speaker         = ndb.StringProperty()
  typeOfSession   = ndb.StringProperty(default="NOT_SPECIFIED")
  date            = ndb.DateProperty()
  startTime       = ndb.TimeProperty()
  endTime         = ndb.TimeProperty()
```

Here, our design choice is that we make the `Session` class as the child of the
`Conference` class. With this approach, it is more easier the query all
sessions in a conference.

Within the `Session` class, the attribute `speaker` is defined as a string. To
avoid the case when two speakers share the same display name, we store the
speaker's id in this string.

Similarly to the field `teeShirtSize`, the attribute `typeOfSession` is
defined as a `enum` with limited value choices.



[1]: https://emguy-122217.appspot.com/_ah/api/explorer
[2]: https://python.org/download/releases/2.7/
[3]: https//cloud.google.com/appengine/downloads
