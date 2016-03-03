# Response to the Reviewer

## Task 1 Design choices (implementation)

```
Please ensure endpoints called out in the requirements are implemented
including: getConferenceSessions (rename getAllSessions)
getConferenceSessionsByType (rename getSessionsByType)
```

These endpoint apis have been properly renamed according to the specification.

## Task 1 Design choices (Response)

```
See note. Unable to decipher your design intention with regards to speaker and
speaker ID
```

Here. This id is the users' google+ account id number. It is similar to user's
email, but it carries much less sensitive information about the user. In this
web application, we retrive this id number through the function
`getUserId(user, id_type="email")` in the provided file `utils.py`. Instead of
passing the default argument `id_type= "email"`, here we pass `id_type="oauth"`
to get the id number associated with the user's google+ account.

## Task 3: additional queries

```
It would not be appropriate to expose the entire Attendee Profile information
to everyone querying this endpoint. This would be highly sensitive to a great
number of people and in fact would violate a number of privacy laws in numerous
jurisdictions.

I would suggest another query focused in on Session information helping people
quickly find sessions they would be interested in.
```

The code in the query api `getAttenderByConference()` has been modified. Now
this api is only open to the conference organizer.



## code readability

(1) Okay. Lots white spaces are included now.
(2) Some inaccurate comments are corrected.
(3) All stale code is removed.

## code reviews
### README.md

#### 1
```
I do not understand your design, could you elaborate on your design decision
with regards to speaker, what is the ID of a speaker? What does a user of your
API expected to provide, where do they get this ID?
```

Here. This id is the users' google+ account id number. It is similar to user's
email, but it carries much less sensitive information about the user. In this
web application, we retrive this id number through the function `getUserId(user,
id_type="email")` in the file `utils.py`. Instead of passing the default
argument `id_type= "email"`, here we pass `id_type="oauth"` to get the id
number associated with the user's google+ account.

#### 2
```
which time queries are you referring to ? could you point out the examples you
implemented making use of endTime beyond the solution suggested in this readme.
```

In task 3, we were asked to query for sessions before 7pm (this could be end
time). 

#### 3
```
Factually incorrect statement
```

Now. That inaccurate statement is revised to the following

"xxxx".

### main.py 
The syntax error at line(7) has been fixed.

### conference.py
```
BooleanMessage and ConflictException have been defined inside models.py and
already imported above starting at line 32.
```

The definitions of the two classes are removed from this file.

#### 2
```
Inaccurate code comment (line 181)
```

All inaccurate comment has been removed.

#### 3
```
Stale code should be removed (line 187)
```

All stale code has been removed from the file.

#### 4
```
conference date objects can be None and this will throw errors (line 204)
```

This bug has been fixed.

#### 5
```
Inaccurate code comment (line 181)
```

All inaccurate comment has been removed.

#### 6

```
this task endpoint does not exist (line 232)

```
xxxxxxxxxxxxx

#### 7
```
Inaccurate code comment (line 232)
```

All inaccurate comment has been removed.

#### 8
```
This method is not available as it follows the same indentation from the
method declared above (line 470)
```

The indentation bug has been corrected.

#### 9
```
This method can be greatly simpified with query filter. (line)
```

xxxxxxxxxxxxxxx

#### 10

```
it would not be appropriate for a public api to expose attendee information
including names and emails addresses to the entire public nor to even
registered conference attendees. (line 944)
```

Now, this query is only open to the conference organizer.
