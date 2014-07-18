""" This module contains facility classes and functions to
access PowerSchool and change the XML data into a more
workable format. """

import mechanize
import base64
import hmac
import md5
import re
import xml.etree.ElementTree as ET
import datetime
import json
import zlib
import xlwt

class Connection:
    """Creates a temporary browser that connects to PowerSchool using HTTP.

    >>> conn = Connection()
    >>> conn.login('http://powerschool.ausd.net', '12345', 'password')
    True
    >>> student = conn.get_student()
    >>> student.first_name
    "Johnny"
    >>> student.gpa
    "2.5"
    """

    def __init__(self):
        self.browser = mechanize.Browser()
        
        self.logged_in = False
        """ (bool) returns whether Connection was able to log in """

        self.error = ''
        """ (string) error message from PowerSchool """

        self.xml_data = None
        """ (string) downloaded XML data """

        self.student = None
        """ (Student) a Student from the Connection """

        self.page = None

    def login(self, url, username, password):
        """ Logs into *url* with credentials *username* and *password*.

        :param url: PowerSchool URL to login into. ex. http://powerschool.ausd.net/
        :type url: string
        :param username: PowerSchool username (usually a Student ID#)
        :type username: string
        :param password: PowerSchool password
        :type password: string

        :returns: **True** if login was successful. Otherwise, **False**.
        """
        self.browser.open(url)  # open URL (http://powerschool.ausd.net/)
        self.browser.select_form(nr=0)  # select first form
        self.browser.form.set_all_readonly(False)  # let us change hidden fields

        ## do login
        pskey = self.browser.form['contextData']  # get pskey

        # The following couple steps imitate PowerSchool's javascript sequence
        b64pw = Connection.b64_md5(password)  # --
        hmac_md5pw = Connection.hex_hmac_md5(pskey, b64pw)  # --
        self.browser.form['account'] = username  # --
        self.browser.form['pw'] = hmac_md5pw  # --
        self.browser.form['dbpw'] = Connection.hex_hmac_md5(pskey, password.lower())  # --
        try:
            # if it's there, set it to unmangled password
            self.browser.form['ldappassword'] = password  # --
        except:
            pass
        self.browser.submit()  # submit form - do login

        rsp = self.browser.response().read()  # get response
        # check if we got an error message
        feedback = re.search(r'<div class="feedback-alert">(.*)</div>', rsp)

        if feedback:
            self.error = feedback.group(1)  # save error
            return False  # failed to login
        else:
            self.logged_in = True  # logged in !
            self.page = self.browser.response().read()  # get page
            return True  # return success

    def get_xml(self):
        """.. note:: Must be logged in to work.

        Downloads the XML data from PowerSchool and returns its contents."""

        if not self.logged_in:
            raise Exception("Not logged in. Cannot download.")
        else:
            if not self.xml_data:
                # assumed logged in, get link
                xml_link = self.browser.find_link(url_regex='studentdata.xml')
                # follow link
                xml_file = self.browser.follow_link(xml_link)
                # download file
                self.xml_data = xml_file.read()
                # return file contents
            return self.xml_data

    def get_student(self):
        """.. note:: Must be logged in to work.

        Create a student from the login information. """
        self.student = Student(self.get_xml())
        return self.student

    def close(self):
        """ Closes the browser instance. """
        self.browser.close()

    @staticmethod
    def b64_md5(code):
        code_md5 = md5.new(code).digest()
        return base64.b64encode(code_md5)[:-2]  # remove padding

    @staticmethod
    def hex_hmac_md5(key, code):
        code_hmac = hmac.new(key, code)
        return code_hmac.hexdigest()

class Student:
    """
    A Student is a data structure that holds: 

    ===========     ==========  ====================
    Field           Type        Description
    ===========     ==========  ====================
    first_name      (string)    First name
    last_name       (string)    Last name
    gender          (string)    Gender (Male/Female)
    gpa             (string)    Grade point average
    courses         (course[])  Courses
    ===========     ==========  ====================

    A course is a dictionary containing:

    ============    ==========   ======================================
    Field           Type         Description
    ============    ==========   ======================================
    name            (string)     Course name
    teacher         (string)     Course teacher (LastName, FirstName)
    letter_grade    (string)     Letter grade received (A, B, C, etc.)
    number_grade    (string)     Number grade received (percentage)
    in_progress     (bool)       Sees if course is to be included
    assignments     (assn[])     Assignments
    categories      (string[])   Categories of assignments for course
    ============    ==========   ======================================

    An assn (assignment) is a dictionary containing:

    ===========     ========     =============================================
    Field           Type         Description
    ===========     ========     =============================================
    name            (string)     Assignment name
    category        (string)     Category of assignment (test, project, etc.)
    due_date        (string)     Due date (Month/Day/Year format)
    score           (float)      Score gotten on assignment
    out_of          (float)      Total amount of points possible
    ===========     ========     =============================================
   
    :param loadstring: XML data to load Student info
    :type loadstring: string
    """
    def __init__(self, loadstring=None):

        self.first_name = ''
        """ (string) First name """

        self.last_name = ''
        """ (string) Last name """

        self.gender = ''
        """ (string) Gender """

        self.gpa = ''
        """ (string) Grade point average """

        self.courses = []
        """ (course[]) Course list """

        self.loaded = False

        if loadstring:
            self.load(loadstring)

    def load(self, loadstring):
        """ Loads a Student with XML data received from loadstring. 

        :param loadstring: XML data to load Student from
        :type loadstring: string"""
        loadstring = loadstring.replace("urn:com:alleyoop:student-record:v0.1.0", "ao")
        root = ET.fromstring(loadstring)
        student = root.find('Student')

        self.first_name = student.find('Person/Name/FirstName').text
        self.last_name = student.find('Person/Name/LastName').text
        self.gender = student.find('Person/Gender/GenderCode').text

        ar = student.find('AcademicRecord')
        self.gpa = ar.find('GPA/GradePointAverage').text

        courses = ar.findall('Course')
        for course in courses:
            # extentions
            # ao -> {ao}
            ext = course.find('UserDefinedExtensions').find('{ao}CourseExtensions')

            tmp_crs = dict()
            tmp_crs['name'] = course.find('CourseTitle').text
            tmp_crs['teacher'] = ext.find('{ao}CourseTeacher').text
            tmp_crs['letter_grade'] = ext.find('{ao}CourseGrade/{ao}CurrentGradeLetter').text
            tmp_crs['number_grade'] = ext.find('{ao}CourseGrade/{ao}CurrentGradeNumeric').text
            tmp_crs['in_progress'] = False
            tmp_crs['assignments'] = []
            tmp_crs['categories'] = []

            assignments = ext.findall('{ao}Assignments/{ao}Assignment')
            for assn in assignments:
                tmp_assn = dict()
                tmp_assn['name'] = assn.find('{ao}Name').text
                tmp_assn['category'] = assn.find('{ao}Category').text

                if tmp_assn['category'] not in tmp_crs['categories']:
                    tmp_crs['categories'].append(tmp_assn['category'])

                tmp_assn['due_date'] = assn.find('{ao}DueDate').text

                grade = re.match(r'(.*)/(.*)', assn.find('{ao}Grade').text)
                
                if grade.group(1) == '--':
                    continue  # skip this assignment

                tmp_assn['score'] = float(grade.group(1))
                tmp_assn['out_of'] = float(grade.group(2))

                tmp_crs['assignments'].append(tmp_assn)

            # sort by due date
            tmp_crs['assignments'].sort(key=lambda c: c['due_date'])
            self.courses.append(tmp_crs)
        self.loaded = True  # finished loading course

    def filter_courses(self, cutoff_date):
        """ Sets each course's *in_progress* attribute to **True** if it is
        between *cutoff_date* and today. 

        :param cutoff_date: Courses between this day (inclusive) will be included.
        :type cutoff_date: datetime.date"""
        for course in self.courses:
            for assn in course['assignments']:
                td = datetime.date.today()
                ms = re.match(r'(\d+)/(\d+)/(\d+)', assn['due_date'])
                (month, day, year) = (int(ms.group(1)), int(ms.group(2)), int(ms.group(3)))
                if cutoff_date <= datetime.date(year, month, day) <= td:
                    course['in_progress'] = True
                    break
            else:
                course['in_progress'] = False

    def to_json(self):
        """.. note:: Requires that the Student has been loaded.

        :returns: Student in JSON format. """

        if not self.loaded:
            raise Exception("Student must first be loaded.")
        
        student_dict = {
            'first_name': self.first_name,
            'last_name': self.last_name,
            'gender': self.gender,
            'gpa': self.gpa,
            'courses': self.courses
        }

        return json.dumps(student_dict, indent=2)

    def z_to_json(self, strength=9):
        """.. note:: Requires that the Student has been loaded.

        Does the same thing as to_json, but compresses the information with
        maximum strength before returning it."""
        return zlib.compress(self.to_json(), strength)

    def to_excel(self):
        """.. note:: Requires that the Student has been loaded.

        :returns: Creates a xlwt Workbook of the Student's grades."""
        if not self.loaded:
            raise Exception("Student must first be loaded.")

        wbk = xlwt.Workbook()

        # set heading styles
        font = xlwt.Font()
        font.bold = True
        style = xlwt.XFStyle()
        style.font = font

        # can be iterated instead of writing sheet.write(...) multiple times
        headers = ('due_date', 'category', 'name', 'score', 'out_of')
        header_full = ('Due Date', 'Category', 'Name', 'Score', 'Out of', '%')

        for course in [course for course in self.courses if course['in_progress']]:
            sheet = wbk.add_sheet(course['name'].replace('/', '.'))  #invchar

            for i, v in enumerate(header_full):  #  for each header tile
                sheet.write(0, i, v, style)  # write it out
            sheet.write(0, 8, "Score", style)
            sheet.write(0, 9, "Points", style)
            sheet.write(0, 10, "% (Weighted)", style)
            sheet.write(4, 8, "Category", style)
            sheet.write(4, 9, "Weight", style)
            sheet.write(4, 10, "Score", style)
            sheet.write(4, 11, "Points", style)
            sheet.write(4, 12, "Avg %", style)

            for i, v in enumerate(course['categories']):
                sheet.write(5 + i, 8, v)
                sheet.write(5 + i, 9, 100)
                sheet.write(5 + i, 10, xlwt.Formula('SUMIF(B2:B1024, "=%s", D2:D1024)' % v))
                sheet.write(5 + i, 11, xlwt.Formula('SUMIF(B2:B1024, "=%s", E2:E1024)' % v))
                sheet.write(5 + i, 12, xlwt.Formula('ROUND(SUMIF(B2:B1024, "=%s", D2:D1024)*100/SUMIF(B2:B1024, "=%s", E2:E1024),2)' % (v,v)))


            for i, assn in enumerate(course['assignments']):  # for each assignment
                for ih, head in enumerate(headers):
                    sheet.write(i + 1, ih, assn[head])  # write row
                if assn['out_of'] != 0:  # (write percentage)
                    sheet.write(i + 1, 5, xlwt.Formula('ROUND(D%d*100/E%d,2)' % (i +2, i + 2)))
                else:
                    sheet.write(i + 1, 5, 100)  # 100% if would case DivByZero
            sheet.write(1, 8, xlwt.Formula('SUM(D1:D1024)'))  # total score
            sheet.write(1, 9, xlwt.Formula('SUM(E1:E1024)'))  # total points
            sheet.write(1, 10, xlwt.Formula('ROUND(SUMPRODUCT(J6:J1024, K6:K1024)*100/SUMPRODUCT(J6:J1024, L6:L1024),2)'))  # percentage

        return wbk
# end document
