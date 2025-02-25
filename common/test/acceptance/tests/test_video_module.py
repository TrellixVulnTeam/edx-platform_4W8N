# -*- coding: utf-8 -*-

"""
Acceptance tests for Video.
"""

import json
import requests
from .helpers import UniqueCourseTest
from ..pages.lms.video import VideoPage
from ..pages.lms.tab_nav import TabNavPage
from ..pages.lms.course_nav import CourseNavPage
from ..pages.lms.auto_auth import AutoAuthPage
from ..pages.lms.course_info import CourseInfoPage
from ..fixtures.course import CourseFixture, XBlockFixtureDesc

VIDEO_SOURCE_PORT = 8777
YOUTUBE_STUB_PORT = 9080
YOUTUBE_STUB_URL = 'http://127.0.0.1:{}/'.format(YOUTUBE_STUB_PORT)

HTML5_SOURCES = [
    'http://localhost:{0}/gizmo.mp4'.format(VIDEO_SOURCE_PORT),
    'http://localhost:{0}/gizmo.webm'.format(VIDEO_SOURCE_PORT),
    'http://localhost:{0}/gizmo.ogv'.format(VIDEO_SOURCE_PORT),
]

HTML5_SOURCES_INCORRECT = [
    'http://localhost:{0}/gizmo.mp99'.format(VIDEO_SOURCE_PORT),
]


class YouTubeConfigError(Exception):
    """
    Error occurred while configuring YouTube Stub Server.
    """
    pass


class VideoBaseTest(UniqueCourseTest):
    """
    Base class for tests of the Video Player
    Sets up the course and provides helper functions for the Video tests.
    """

    def setUp(self):
        """
        Initialization of pages and course fixture for video tests
        """
        super(VideoBaseTest, self).setUp()

        self.video = VideoPage(self.browser)
        self.tab_nav = TabNavPage(self.browser)
        self.course_nav = CourseNavPage(self.browser)
        self.course_info_page = CourseInfoPage(self.browser, self.course_id)

        self.course_fixture = CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        )

        self.metadata = None
        self.assets = []
        self.verticals = None
        self.youtube_configuration = {}

        # reset youtube stub server
        self.addCleanup(self._reset_youtube_stub_server)

    def navigate_to_video(self):
        """ Prepare the course and get to the video and render it """
        self._install_course_fixture()
        self._navigate_to_courseware_video_and_render()

    def navigate_to_video_no_render(self):
        """
        Prepare the course and get to the video unit
        however do not wait for it to render, because
        the has been an error.
        """
        self._install_course_fixture()
        self._navigate_to_courseware_video_no_render()

    def _install_course_fixture(self):
        """ Install the course fixture that has been defined """
        if self.assets:
            self.course_fixture.add_asset(self.assets)

        chapter_sequential = XBlockFixtureDesc('sequential', 'Test Section')
        chapter_sequential.add_children(*self._add_course_verticals())
        chapter = XBlockFixtureDesc('chapter', 'Test Chapter').add_children(chapter_sequential)
        self.course_fixture.add_children(chapter)
        self.course_fixture.install()

        if len(self.youtube_configuration) > 0:
            self._configure_youtube_stub_server(self.youtube_configuration)

    def _add_course_verticals(self):
        """
        Create XBlockFixtureDesc verticals
        :return: a list of XBlockFixtureDesc
        """
        xblock_verticals = []
        _verticals = self.verticals

        # Video tests require at least one vertical with a single video.
        if not _verticals:
            _verticals = [[{'display_name': 'Video', 'metadata': self.metadata}]]

        for vertical_index, vertical in enumerate(_verticals):
            xblock_verticals.append(self._create_single_vertical(vertical, vertical_index))

        return xblock_verticals

    def _create_single_vertical(self, vertical, vertical_index):
        """
        Create a single course vertical of type XBlockFixtureDesc with category `vertical`.
        A single course vertical can contain single or multiple video modules.
        :param vertical: vertical data list
        :param vertical_index: index for the vertical display name
        :return: XBlockFixtureDesc
        """
        xblock_course_vertical = XBlockFixtureDesc('vertical', 'Test Vertical-{0}'.format(vertical_index))

        for video in vertical:
            xblock_course_vertical.add_children(
                XBlockFixtureDesc('video', video['display_name'], metadata=video.get('metadata')))

        return xblock_course_vertical

    def _navigate_to_courseware_video(self):
        """ Register for the course and navigate to the video unit """
        AutoAuthPage(self.browser, course_id=self.course_id).visit()

        self.course_info_page.visit()
        self.tab_nav.go_to_tab('Courseware')

    def _navigate_to_courseware_video_and_render(self):
        """ Wait for the video player to render """
        self._navigate_to_courseware_video()
        self.video.wait_for_video_player_render()

    def _navigate_to_courseware_video_no_render(self):
        """ Wait for the video Xmodule but not for rendering """
        self._navigate_to_courseware_video()
        self.video.wait_for_video_class()

    def _configure_youtube_stub_server(self, config):
        """
        Allow callers to configure the stub server using the /set_config URL.
        :param config: Configuration dictionary.
        The request should have PUT data, such that:
            Each PUT parameter is the configuration key.
            Each PUT value is a JSON-encoded string value for the configuration.
        :raise YouTubeConfigError:
        """
        youtube_stub_config_url = YOUTUBE_STUB_URL + 'set_config'

        config_data = {param: json.dumps(value) for param, value in config.items()}
        response = requests.put(youtube_stub_config_url, data=config_data)

        if not response.ok:
            raise YouTubeConfigError(
                'YouTube Server Configuration Failed. URL {0}, Configuration Data: {1}, Status was {2}'.format(
                    youtube_stub_config_url, config, response.status_code))

    def _reset_youtube_stub_server(self):
        """
        Reset YouTube Stub Server Configurations using the /del_config URL.
        :raise YouTubeConfigError:
        """
        youtube_stub_config_url = YOUTUBE_STUB_URL + 'del_config'

        response = requests.delete(youtube_stub_config_url)

        if not response.ok:
            raise YouTubeConfigError(
                'YouTube Server Configuration Failed. URL: {0} Status was {1}'.format(
                    youtube_stub_config_url, response.status_code))

    def metadata_for_mode(self, player_mode, additional_data=None):
        """
        Create a dictionary for video player configuration according to `player_mode`
        :param player_mode (str): Video player mode
        :param additional_data (dict): Optional additional metadata.
        :return: dict
        """
        metadata = {}

        if player_mode == 'html5':
            metadata.update({
                'youtube_id_1_0': '',
                'youtube_id_0_75': '',
                'youtube_id_1_25': '',
                'youtube_id_1_5': '',
                'html5_sources': HTML5_SOURCES
            })

        if player_mode == 'youtube_html5':
            metadata.update({
                'html5_sources': HTML5_SOURCES,
            })

        if player_mode == 'youtube_html5_unsupported_video':
            metadata.update({
                'html5_sources': HTML5_SOURCES_INCORRECT
            })

        if player_mode == 'html5_unsupported_video':
            metadata.update({
                'youtube_id_1_0': '',
                'youtube_id_0_75': '',
                'youtube_id_1_25': '',
                'youtube_id_1_5': '',
                'html5_sources': HTML5_SOURCES_INCORRECT
            })

        if additional_data:
            metadata.update(additional_data)

        return metadata

    def open_video(self, video_display_name):
        """
        Navigate to sequential specified by `video_display_name`
        :param video_display_name (str): Sequential Title
        """
        self.course_nav.go_to_sequential(video_display_name)
        self.video.wait_for_video_player_render()


class YouTubeVideoTest(VideoBaseTest):
    """ Test YouTube Video Player """

    def setUp(self):
        super(YouTubeVideoTest, self).setUp()

    def test_youtube_video_rendering_wo_html5_sources(self):
        """
        Scenario: Video component is rendered in the LMS in Youtube mode without HTML5 sources
        Given the course has a Video component in "Youtube" mode
        Then the video has rendered in "Youtube" mode
        """
        self.navigate_to_video()

        # Verify that video has rendered in "Youtube" mode
        self.assertTrue(self.video.is_video_rendered('youtube'))

    def test_cc_button_wo_english_transcript(self):
        """
        Scenario: CC button works correctly w/o english transcript in Youtube mode
        Given the course has a Video component in "Youtube" mode
        And I have defined a non-english transcript for the video
        And I have uploaded a non-english transcript file to assets
        Then I see the correct text in the captions
        """
        data = {'transcripts': {'zh': 'chinese_transcripts.srt'}}
        self.metadata = self.metadata_for_mode('youtube', data)
        self.assets.append('chinese_transcripts.srt')
        self.navigate_to_video()
        self.video.show_captions()

        # Verify that we see "好 各位同学" text in the captions
        unicode_text = "好 各位同学".decode('utf-8')
        self.assertIn(unicode_text, self.video.captions_text)

    def test_cc_button_transcripts_and_sub_fields_empty(self):
        """
        Scenario: CC button works correctly if transcripts and sub fields are empty,
            but transcript file exists in assets (Youtube mode of Video component)
        Given the course has a Video component in "Youtube" mode
        And I have uploaded a .srt.sjson file to assets
        Then I see the correct english text in the captions
        """
        self.assets.append('subs_OEoXaMPEzfM.srt.sjson')
        self.navigate_to_video()
        self.video.show_captions()

        # Verify that we see "Hi, welcome to Edx." text in the captions
        self.assertIn('Hi, welcome to Edx.', self.video.captions_text)

    def test_cc_button_hidden_no_translations(self):
        """
        Scenario: CC button is hidden if no translations
        Given the course has a Video component in "Youtube" mode
        Then the "CC" button is hidden
        """
        self.navigate_to_video()
        self.assertFalse(self.video.is_button_shown('CC'))

    def test_fullscreen_video_alignment_with_transcript_hidden(self):
        """
        Scenario: Video is aligned with transcript hidden in fullscreen mode
        Given the course has a Video component in "Youtube" mode
        When I view the video at fullscreen
        Then the video with the transcript hidden is aligned correctly
        """
        self.navigate_to_video()

        # click video button "fullscreen"
        self.video.click_player_button('fullscreen')

        # check if video aligned correctly without enabled transcript
        self.assertTrue(self.video.is_aligned(False))

    def test_download_button_wo_english_transcript(self):
        """
        Scenario: Download button works correctly w/o english transcript in YouTube mode
        Given the course has a Video component in "Youtube" mode
        And I have defined a downloadable non-english transcript for the video
        And I have uploaded a non-english transcript file to assets
        Then I can download the transcript in "srt" format
        """
        data = {'download_track': True, 'transcripts': {'zh': 'chinese_transcripts.srt'}}
        self.metadata = self.metadata_for_mode('youtube', additional_data=data)
        self.assets.append('chinese_transcripts.srt')

        # go to video
        self.navigate_to_video()

        # check if we can download transcript in "srt" format that has text "好 各位同学"
        unicode_text = "好 各位同学".decode('utf-8')
        self.assertTrue(self.video.downloaded_transcript_contains_text('srt', unicode_text))

    def test_download_button_two_transcript_languages(self):
        """
        Scenario: Download button works correctly for multiple transcript languages
        Given the course has a Video component in "Youtube" mode
        And I have defined a downloadable non-english transcript for the video
        And I have defined english subtitles for the video
        Then I see the correct english text in the captions
        And the english transcript downloads correctly
        And I see the correct non-english text in the captions
        And the non-english transcript downloads correctly
        """
        self.assets.extend(['chinese_transcripts.srt', 'subs_OEoXaMPEzfM.srt.sjson'])
        data = {'download_track': True, 'transcripts': {'zh': 'chinese_transcripts.srt'}, 'sub': 'OEoXaMPEzfM'}
        self.metadata = self.metadata_for_mode('youtube', additional_data=data)

        # go to video
        self.navigate_to_video()

        # check if "Hi, welcome to Edx." text in the captions
        self.assertIn('Hi, welcome to Edx.', self.video.captions_text)

        # check if we can download transcript in "srt" format that has text "Hi, welcome to Edx."
        self.assertTrue(self.video.downloaded_transcript_contains_text('srt', 'Hi, welcome to Edx.'))

        # select language with code "zh"
        self.assertTrue(self.video.select_language('zh'))

        # check if we see "好 各位同学" text in the captions
        unicode_text = "好 各位同学".decode('utf-8')
        self.assertIn(unicode_text, self.video.captions_text)

        # check if we can download transcript in "srt" format that has text "好 各位同学"
        unicode_text = "好 各位同学".decode('utf-8')
        self.assertTrue(self.video.downloaded_transcript_contains_text('srt', unicode_text))

    def test_fullscreen_video_alignment_on_transcript_toggle(self):
        """
        Scenario: Video is aligned correctly on transcript toggle in fullscreen mode
        Given the course has a Video component in "Youtube" mode
        And I have uploaded a .srt.sjson file to assets
        And I have defined subtitles for the video
        When I view the video at fullscreen
        Then the video with the transcript enabled is aligned correctly
        And the video with the transcript hidden is aligned correctly
        """
        self.assets.append('subs_OEoXaMPEzfM.srt.sjson')
        data = {'sub': 'OEoXaMPEzfM'}
        self.metadata = self.metadata_for_mode('youtube', additional_data=data)

        # go to video
        self.navigate_to_video()

        # make sure captions are opened
        self.video.show_captions()

        # click video button "fullscreen"
        self.video.click_player_button('fullscreen')

        # check if video aligned correctly with enabled transcript
        self.assertTrue(self.video.is_aligned(True))

        # click video button "CC"
        self.video.click_player_button('CC')

        # check if video aligned correctly without enabled transcript
        self.assertTrue(self.video.is_aligned(False))

    def test_video_rendering_with_default_response_time(self):
        """
        Scenario: Video is rendered in Youtube mode when the YouTube Server responds quickly
        Given the YouTube server response time less than 1.5 seconds
        And the course has a Video component in "Youtube_HTML5" mode
        Then the video has rendered in "Youtube" mode
        """
        # configure youtube server
        self.youtube_configuration['time_to_response'] = 0.4
        self.metadata = self.metadata_for_mode('youtube_html5')

        self.navigate_to_video()

        self.assertTrue(self.video.is_video_rendered('youtube'))

    def test_video_rendering_wo_default_response_time(self):
        """
        Scenario: Video is rendered in HTML5 when the YouTube Server responds slowly
        Given the YouTube server response time is greater than 1.5 seconds
        And the course has a Video component in "Youtube_HTML5" mode
        Then the video has rendered in "HTML5" mode
        """
        # configure youtube server
        self.youtube_configuration['time_to_response'] = 2.0
        self.metadata = self.metadata_for_mode('youtube_html5')

        self.navigate_to_video()

        self.assertTrue(self.video.is_video_rendered('html5'))

    def test_video_with_youtube_blocked(self):
        """
        Scenario: Video is rendered in HTML5 mode when the YouTube API is blocked
        Given the YouTube server response time is greater than 1.5 seconds
        And the YouTube API is blocked
        And the course has a Video component in "Youtube_HTML5" mode
        Then the video has rendered in "HTML5" mode
        """
        # configure youtube server
        self.youtube_configuration.update({
            'time_to_response': 2.0,
            'youtube_api_blocked': True,
        })
        self.metadata = self.metadata_for_mode('youtube_html5')

        self.navigate_to_video()

        self.assertTrue(self.video.is_video_rendered('html5'))

    def test_download_transcript_button_works_correctly(self):
        """
        Scenario: Download Transcript button works correctly
        Given the course has Video components A and B in "Youtube" mode
        And Video component C in "HTML5" mode
        And I have defined downloadable transcripts for the videos
        Then I can download a transcript for Video A in "srt" format
        And I can download a transcript for Video A in "txt" format
        And I can download a transcript for Video B in "txt" format
        And the Download Transcript menu does not exist for Video C
        """

        data_a = {'sub': 'OEoXaMPEzfM', 'download_track': True}
        youtube_a_metadata = self.metadata_for_mode('youtube', additional_data=data_a)
        self.assets.append('subs_OEoXaMPEzfM.srt.sjson')

        data_b = {'youtube_id_1_0': 'b7xgknqkQk8', 'sub': 'b7xgknqkQk8', 'download_track': True}
        youtube_b_metadata = self.metadata_for_mode('youtube', additional_data=data_b)
        self.assets.append('subs_b7xgknqkQk8.srt.sjson')

        data_c = {'track': 'http://example.org/', 'download_track': True}
        html5_c_metadata = self.metadata_for_mode('html5', additional_data=data_c)

        self.verticals = [
            [{'display_name': 'A', 'metadata': youtube_a_metadata}],
            [{'display_name': 'B', 'metadata': youtube_b_metadata}],
            [{'display_name': 'C', 'metadata': html5_c_metadata}]
        ]

        # open the section with videos (open video "A")
        self.navigate_to_video()

        # check if we can download transcript in "srt" format that has text "00:00:00,270"
        self.assertTrue(self.video.downloaded_transcript_contains_text('srt', '00:00:00,270'))

        # select the transcript format "txt"
        self.assertTrue(self.video.select_transcript_format('txt'))

        # check if we can download transcript in "txt" format that has text "Hi, welcome to Edx."
        self.assertTrue(self.video.downloaded_transcript_contains_text('txt', 'Hi, welcome to Edx.'))

        # open video "B"
        self.course_nav.go_to_sequential('B')

        # check if we can download transcript in "txt" format that has text "Equal transcripts"
        self.assertTrue(self.video.downloaded_transcript_contains_text('txt', 'Equal transcripts'))

        # open video "C"
        self.course_nav.go_to_sequential('C')

        # menu "download_transcript" doesn't exist
        self.assertFalse(self.video.is_menu_exist('download_transcript'))

    def test_video_language_menu_working(self):
        """
        Scenario: Language menu works correctly in Video component
        Given the course has a Video component in "Youtube" mode
        And I have defined multiple language transcripts for the videos
        And I make sure captions are closed
        And I see video menu "language" with correct items
        And I select language with code "zh"
        Then I see "好 各位同学" text in the captions
        And I select language with code "en"
        Then I see "Hi, welcome to Edx." text in the captions
        """
        self.assets.extend(['chinese_transcripts.srt', 'subs_OEoXaMPEzfM.srt.sjson'])
        data = {'transcripts': {"zh": "chinese_transcripts.srt"}, 'sub': 'OEoXaMPEzfM'}
        self.metadata = self.metadata_for_mode('youtube', additional_data=data)

        # go to video
        self.navigate_to_video()

        self.video.hide_captions()

        correct_languages = {'en': 'English', 'zh': 'Chinese'}
        self.assertEqual(self.video.caption_languages(), correct_languages)

        self.video.select_language('zh')

        unicode_text = "好 各位同学".decode('utf-8')
        self.assertIn(unicode_text, self.video.captions_text)

        self.video.select_language('en')
        self.assertIn('Hi, welcome to Edx.', self.video.captions_text)


class YouTubeHtml5VideoTest(VideoBaseTest):
    """ Test YouTube HTML5 Video Player """

    def setUp(self):
        super(YouTubeHtml5VideoTest, self).setUp()

    def test_youtube_video_rendering_with_unsupported_sources(self):
        """
        Scenario: Video component is rendered in the LMS in Youtube mode
            with HTML5 sources that doesn't supported by browser
        Given the course has a Video component in "Youtube_HTML5_Unsupported_Video" mode
        Then the video has rendered in "Youtube" mode
        """
        self.metadata = self.metadata_for_mode('youtube_html5_unsupported_video')
        self.navigate_to_video()

        # Verify that the video has rendered in "Youtube" mode
        self.assertTrue(self.video.is_video_rendered('youtube'))


class Html5VideoTest(VideoBaseTest):
    """ Test HTML5 Video Player """

    def setUp(self):
        super(Html5VideoTest, self).setUp()

    def test_autoplay_disabled_for_video_component(self):
        """
        Scenario: Autoplay is disabled by default for a Video component
        Given the course has a Video component in "HTML5" mode
        When I view the Video component
        Then it does not have autoplay enabled
        """
        self.metadata = self.metadata_for_mode('html5')
        self.navigate_to_video()

        # Verify that the video has autoplay mode disabled
        self.assertFalse(self.video.is_autoplay_enabled)

    def test_html5_video_rendering_with_unsupported_sources(self):
        """
        Scenario: LMS displays an error message for HTML5 sources that are not supported by browser
        Given the course has a Video component in "HTML5_Unsupported_Video" mode
        When I view the Video component
        Then and error message is shown
        And the error message has the correct text
        """
        self.metadata = self.metadata_for_mode('html5_unsupported_video')
        self.navigate_to_video_no_render()

        # Verify that error message is shown
        self.assertTrue(self.video.is_error_message_shown)

        # Verify that error message has correct text
        correct_error_message_text = 'No playable video sources found.'
        self.assertIn(correct_error_message_text, self.video.error_message_text)

        # Verify that spinner is not shown
        self.assertFalse(self.video.is_spinner_shown())

    def test_download_button_wo_english_transcript(self):
        """
        Scenario: Download button works correctly w/o english transcript in HTML5 mode
        Given the course has a Video component in "HTML5" mode
        And I have defined a downloadable non-english transcript for the video
        And I have uploaded a non-english transcript file to assets
        Then I see the correct non-english text in the captions
        And the non-english transcript downloads correctly
        """
        data = {'download_track': True, 'transcripts': {'zh': 'chinese_transcripts.srt'}}
        self.metadata = self.metadata_for_mode('html5', additional_data=data)
        self.assets.append('chinese_transcripts.srt')

        # go to video
        self.navigate_to_video()

        # check if we see "好 各位同学" text in the captions
        unicode_text = "好 各位同学".decode('utf-8')
        self.assertIn(unicode_text, self.video.captions_text)

        # check if we can download transcript in "srt" format that has text "好 各位同学"
        unicode_text = "好 各位同学".decode('utf-8')
        self.assertTrue(self.video.downloaded_transcript_contains_text('srt', unicode_text))

    def test_download_button_two_transcript_languages(self):
        """
        Scenario: Download button works correctly for multiple transcript languages in HTML5 mode
        Given the course has a Video component in "HTML5" mode
        And I have defined a downloadable non-english transcript for the video
        And I have defined english subtitles for the video
        Then I see the correct english text in the captions
        And the english transcript downloads correctly
        And I see the correct non-english text in the captions
        And the non-english transcript downloads correctly
        """
        self.assets.extend(['chinese_transcripts.srt', 'subs_OEoXaMPEzfM.srt.sjson'])
        data = {'download_track': True, 'transcripts': {'zh': 'chinese_transcripts.srt'}, 'sub': 'OEoXaMPEzfM'}
        self.metadata = self.metadata_for_mode('html5', additional_data=data)

        # go to video
        self.navigate_to_video()

        # check if "Hi, welcome to Edx." text in the captions
        self.assertIn('Hi, welcome to Edx.', self.video.captions_text)

        # check if we can download transcript in "srt" format that has text "Hi, welcome to Edx."
        self.assertTrue(self.video.downloaded_transcript_contains_text('srt', 'Hi, welcome to Edx.'))

        # select language with code "zh"
        self.assertTrue(self.video.select_language('zh'))

        # check if we see "好 各位同学" text in the captions
        unicode_text = "好 各位同学".decode('utf-8')

        self.assertIn(unicode_text, self.video.captions_text)

        #Then I can download transcript in "srt" format that has text "好 各位同学"
        unicode_text = "好 各位同学".decode('utf-8')
        self.assertTrue(self.video.downloaded_transcript_contains_text('srt', unicode_text))

    def test_full_screen_video_alignment_with_transcript_visible(self):
        """
        Scenario: Video is aligned correctly with transcript enabled in fullscreen mode
        Given the course has a Video component in "HTML5" mode
        And I have uploaded a .srt.sjson file to assets
        And I have defined subtitles for the video
        When I show the captions
        And I view the video at fullscreen
        Then the video with the transcript enabled is aligned correctly
        """
        self.assets.append('subs_OEoXaMPEzfM.srt.sjson')
        data = {'sub': 'OEoXaMPEzfM'}
        self.metadata = self.metadata_for_mode('html5', additional_data=data)

        # go to video
        self.navigate_to_video()

        # make sure captions are opened
        self.video.show_captions()

        # click video button "fullscreen"
        self.video.click_player_button('fullscreen')

        # check if video aligned correctly with enabled transcript
        self.assertTrue(self.video.is_aligned(True))

    def test_cc_button_with_english_transcript(self):
        """
        Scenario: CC button works correctly with only english transcript in HTML5 mode
        Given the course has a Video component in "HTML5" mode
        And I have defined english subtitles for the video
        And I have uploaded an english transcript file to assets
        Then I see the correct text in the captions
        """
        self.assets.append('subs_OEoXaMPEzfM.srt.sjson')
        data = {'sub': 'OEoXaMPEzfM'}
        self.metadata = self.metadata_for_mode('html5', additional_data=data)

        # go to video
        self.navigate_to_video()

        # make sure captions are opened
        self.video.show_captions()

        # check if we see "Hi, welcome to Edx." text in the captions
        self.assertIn("Hi, welcome to Edx.", self.video.captions_text)

    def test_cc_button_wo_english_transcript(self):
        """
        Scenario: CC button works correctly w/o english transcript in HTML5 mode
        Given the course has a Video component in "HTML5" mode
        And I have defined a non-english transcript for the video
        And I have uploaded a non-english transcript file to assets
        Then I see the correct text in the captions
        """
        self.assets.append('chinese_transcripts.srt')
        data = {'transcripts': {'zh': 'chinese_transcripts.srt'}}
        self.metadata = self.metadata_for_mode('html5', additional_data=data)

        # go to video
        self.navigate_to_video()

        # make sure captions are opened
        self.video.show_captions()

        # check if we see "好 各位同学" text in the captions
        unicode_text = "好 各位同学".decode('utf-8')
        self.assertIn(unicode_text, self.video.captions_text)

    def test_video_rendering(self):
        """
        Scenario: Video component is fully rendered in the LMS in HTML5 mode
        Given the course has a Video component in "HTML5" mode
        Then the video has rendered in "HTML5" mode
        And video sources are correct
        """
        self.metadata = self.metadata_for_mode('html5')

        self.navigate_to_video()

        self.assertTrue(self.video.is_video_rendered('html5'))

        self.assertTrue(all([source in HTML5_SOURCES for source in self.video.sources()]))
