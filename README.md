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
2. [Google App Engine SDK for Python][3]

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
`Conference` class. With this approach, it is more easier to query all
sessions in a conference.

Within the `Session` class, the attribute `speaker` is declared as a string. To
avoid the case when two speakers share the same display name, we store the
speaker's id in this string.

Similarly to the field `teeShirtSize` of the `Profile` class, the attribute
`typeOfSession` is declared as a `enum` with limited value choices.

In addition, instead of saving `duration` in the class, here we store the
`endTime` of the session. This attribute is of the same type as
`startTime`. This approach simplifies the implementation of time queries for
sessions.

## Two additional queries

The following two additional queries are implemented on the API server.

- `getAttenderByConference(websafeConferenceKey)` -- Given a conference, return all attenders.

```Python
query_result = Profile.query(Profile.conferenceKeysToAttend.IN([websafeConferenceKey,]))
```

- `getAllSessionByDate(websafeConferenceKey, dateString)` -- Given a conference and a date, return all sessions on that day.

```Python
query_result = Session.query(ancestor=c_key)
query_result = query_result.filter(Session.date==datetime.strptime(request.date, "%Y-%m-%d").date())
```

## Query problem: How would you handle a query for all non-workshop sessions before 7pm?

Google cloud datastore only allows ONE inequality filter for each query.

One approach to solve this query problem is that we only do the query by time
(before 7:00pm) on all sessions in the given conference as:

```Python
query_result = Session.query(ancestor=conf.key).filter(Session.endTime<=time(19, 00))

```
Then, the additional filtering on `typeOfSession` can be achieved by applying the
following python logic:
```Python
query_result = [session for session in query_result if session.typeOfSession != "Workshop"]

```

Report bugs to <emguy2000@gmail.com>.

[1]: https://emguy-122217.appspot.com/_ah/api/explorer
[2]: https://python.org/download/releases/2.7/
[3]: https//cloud.google.com/appengine/downloads
