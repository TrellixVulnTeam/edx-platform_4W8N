import logging
from django.core.management.base import BaseCommand, CommandError
from certificates.models import certificate_status_for_student
from certificates.queue import XQueueCertInterface
from django.contrib.auth.models import User
from optparse import make_option
from django.conf import settings
from opaque_keys import InvalidKeyError
from xmodule.modulestore.keys import CourseKey
from xmodule.modulestore.locations import SlashSeparatedCourseKey
from xmodule.course_module import CourseDescriptor
from xmodule.modulestore.django import modulestore
from certificates.models import CertificateStatuses
import datetime
from pytz import UTC

log = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """
    Find all students that need certificates for courses that have finished and
    put their cert requests on the queue.

    If --user is given, only grade and certify the requested username.

    Use the --noop option to test without actually putting certificates on the
    queue to be generated.
    """

    option_list = BaseCommand.option_list + (
        make_option('-n', '--noop',
                    action='store_true',
                    dest='noop',
                    default=False,
                    help="Don't add certificate requests to the queue"),
        make_option('--insecure',
                    action='store_true',
                    dest='insecure',
                    default=False,
                    help="Don't use https for the callback url to the LMS, useful in http test environments"),
        make_option('-c', '--course',
                    metavar='COURSE_ID',
                    dest='course',
                    default=False,
                    help='Grade and generate certificates '
                    'for a specific course'),
        make_option('-f', '--force-gen',
                    metavar='STATUS',
                    dest='force',
                    default=False,
                    help='Will generate new certificates for only those users '
                    'whose entry in the certificate table matches STATUS. '
                    'STATUS can be generating, unavailable, deleted, error '
                    'or notpassing.'),
    )

    def handle(self, *args, **options):

        # Will only generate a certificate if the current
        # status is in the unavailable state, can be set
        # to something else with the force flag

        if options['force']:
            valid_statuses = getattr(CertificateStatuses, options['force'])
        else:
            valid_statuses = [CertificateStatuses.unavailable]

        # Print update after this many students

        STATUS_INTERVAL = 500

        course_id = options['course']
        if course_id:
            # try to parse out the course from the serialized form
            try:
                course = CourseKey.from_string(course_id)
            except InvalidKeyError:
                log.warning("Course id %s could not be parsed as a CourseKey; falling back to SSCK.from_dep_str", course_id)
                course = SlashSeparatedCourseKey.from_deprecated_string(course_id)
            ended_courses = [course]
        else:
            raise CommandError("You must specify a course")

        for course_key in ended_courses:
            # prefetch all chapters/sequentials by saying depth=2
            course = modulestore().get_course(course_key, depth=2)

            org, course_str, run = course_id.split('/')
            slashseparatedcoursekey = SlashSeparatedCourseKey(org, course_str, run)

            print "Fetching enrolled students for {0}".format(course_key.to_deprecated_string())
            enrolled_students = User.objects.filter(
                courseenrollment__course_id=slashseparatedcoursekey)

            xq = XQueueCertInterface()
            if options['insecure']:
                xq.use_https = False
            total = enrolled_students.count()
            count = 0
            start = datetime.datetime.now(UTC)

            print "Found {0} enrolled students for {1}".format(total, course_key.to_deprecated_string())

            for student in enrolled_students:
                count += 1
                if count % STATUS_INTERVAL == 0:
                    # Print a status update with an approximation of
                    # how much time is left based on how long the last
                    # interval took
                    diff = datetime.datetime.now(UTC) - start
                    timeleft = diff * (total - count) / STATUS_INTERVAL
                    hours, remainder = divmod(timeleft.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    print "{0}/{1} completed ~{2:02}:{3:02}m remaining".format(
                        count, total, hours, minutes)
                    start = datetime.datetime.now(UTC)

                if certificate_status_for_student(
                        student, course_key)['status'] in valid_statuses:
                    if not options['noop']:
                        # Add the certificate request to the queue
                        ret = xq.add_cert(student, course_key, course=course)
                        if ret == 'generating':
                            print '{0} - {1}'.format(student, ret)
