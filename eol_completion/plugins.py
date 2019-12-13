from django.conf import settings
from django.utils.translation import ugettext_noop

from courseware.tabs import EnrolledTab
import django_comment_client.utils as utils
from xmodule.tabs import TabFragmentViewMixin

class EolCompletionTab(TabFragmentViewMixin, EnrolledTab):
    type = 'eol_completion'
    title = ugettext_noop('Completion')
    priority = None
    view_name = 'completion_view'
    fragment_view_name = 'eol_completion.views.EolCompletionFragmentView'
    is_hideable = True
    is_default = True
    body_class = 'eol_completion'
    online_help_token = 'eol_completion'

    @classmethod
    def is_enabled(cls, course, user=None):
        return True