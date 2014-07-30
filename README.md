ps.py
=====

A PowerSchool authentication &amp; data fetching library implemented in Python.

Inspired by [ScorePortal](http://www.scoreportal.org).

More details & API reference [here](http://ouiliame.github.io/ps.py).

***NOTE:*** This was written more than a year ago, and last I checked it was working fine. However, PowerSchool may have undergone upgrades which could disrupt the functionality of this library. Also, I was only able to test it with AUSD's PowerSchool, so it may or may not work for other districts.

## Installation ##

Extract the contents of the archive to a folder and run:

`$ python setup.py install`

## Example ##
This example shows how one can use **ps.py** to login to PowerSchool and fetch grades.

```python
import ps

# Credentials
URL = 'http://powerschool.ausd.net/'
USERNAME = '12345'
PASSWORD = 'j83nl3a'

# Connect to PowerSchool
conn = ps.Connection()

# check if logged in
if conn.login(URL, USERNAME, PASSWORD):

	# get Student instance
	student = conn.get_student()

	# output a JSON file
	with open('12345.json', 'w') as file:
		file.write(student.to_json())

	# process info
	print "Hi there, " + student.first_name
	print "Your GPA: " + student.gpa
	print "Your classes:"

	for course in student.courses:
		print course.name, course.letter_grade, course.number_grade
		print "Assignments:"
		for assn in course.assignments:
			print assn.due_date, assn.category, assn.name

else:
	print 'Could not log in: ' + conn.error

# we're done, close the object.
conn.close()

```
