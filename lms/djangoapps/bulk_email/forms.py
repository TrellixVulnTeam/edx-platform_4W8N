"""
Defines a form for providing validation of CourseEmail templates.
"""
import logging

from django import forms
from django.core.exceptions import ValidationError

from bulk_email.models import CourseEmailTemplate, COURSE_EMAIL_MESSAGE_BODY_TAG, CourseAuthorization

from opaque_keys import InvalidKeyError
from xmodule.modulestore import XML_MODULESTORE_TYPE
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.locations import SlashSeparatedCourseKey

log = logging.getLogger(__name__)


class CourseEmailTemplateForm(forms.ModelForm):  # pylint: disable=R0924
    """Form providing validation of CourseEmail templates."""

    class Meta:  # pylint: disable=C0111
        model = CourseEmailTemplate

    def _validate_template(self, template):
        """Check the template for required tags."""
        index = template.find(COURSE_EMAIL_MESSAGE_BODY_TAG)
        if index < 0:
            msg = 'Missing tag: "{}"'.format(COURSE_EMAIL_MESSAGE_BODY_TAG)
            log.warning(msg)
            raise ValidationError(msg)
        if template.find(COURSE_EMAIL_MESSAGE_BODY_TAG, index + 1) >= 0:
            msg = 'Multiple instances of tag: "{}"'.format(COURSE_EMAIL_MESSAGE_BODY_TAG)
            log.warning(msg)
            raise ValidationError(msg)
        # TODO: add more validation here, including the set of known tags
        # for which values will be supplied.  (Email will fail if the template
        # uses tags for which values are not supplied.)

    def clean_html_template(self):
        """Validate the HTML template."""
        template = self.cleaned_data["html_template"]
        self._validate_template(template)
        return template

    def clean_plain_template(self):
        """Validate the plaintext template."""
        template = self.cleaned_data["plain_template"]
        self._validate_template(template)
        return template


class CourseAuthorizationAdminForm(forms.ModelForm):  # pylint: disable=R0924
    """Input form for email enabling, allowing us to verify data."""

    class Meta:  # pylint: disable=C0111
        model = CourseAuthorization

    def clean_course_id(self):
        """Validate the course id"""
        cleaned_id = self.cleaned_data["course_id"]
        try:
            course_id = SlashSeparatedCourseKey.from_deprecated_string(cleaned_id)
        except InvalidKeyError:
            msg = u'Course id invalid.' 
            msg += u' --- Entered course id was: "{0}". '.format(cleaned_id)
            msg += 'Please recheck that you have supplied a valid course id.'
            raise forms.ValidationError(msg)

        if not modulestore().has_course(course_id):
            msg = u'COURSE NOT FOUND'
            msg += u' --- Entered course id was: "{0}". '.format(course_id.to_deprecated_string())
            msg += 'Please recheck that you have supplied a valid course id.'
            raise forms.ValidationError(msg)

        # Now, try and discern if it is a Studio course - HTML editor doesn't work with XML courses
        is_studio_course = modulestore().get_modulestore_type(course_id) != XML_MODULESTORE_TYPE
        if not is_studio_course:
            msg = "Course Email feature is only available for courses authored in Studio. "
            msg += '"{0}" appears to be an XML backed course.'.format(course_id.to_deprecated_string())
            raise forms.ValidationError(msg)

        return course_id.to_deprecated_string()
