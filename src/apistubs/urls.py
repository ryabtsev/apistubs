from django.urls import re_path as url

from apistubs import settings as su_settings

app_name = 'apistubs'
urlpatterns = []

if su_settings.ENABLED:
    from apistubs.views.common import (
        IndexView,
        BrowserView,
        OAuth2RedirectView,
        SpecView,
    )
    from apistubs.views.stub import (
        StubView,
    )
    from apistubs.views.prompt import (
        PromptView,
        PromptAPIView,
    )
    from apistubs.views.logging import (
        LogView,
    )

    urlpatterns += [
        url(r'^browser/$', BrowserView.as_view(), name='browser', kwargs={'SSL': 3}),
    ]

    urlpatterns += [
        url(r'^$', IndexView.as_view(), name='index_default'),
    ]

    urlpatterns += [
        url(r'^stub/', StubView.as_view(), name='stub_default'),
        url(r'^api.json$', SpecView.as_view(), name='spec_default'),
        url(r'^prompt/$', PromptView.as_view(), name='prompt_index'),
        url(r'^prompt/api/$', PromptAPIView.as_view(), name='prompt'),
        url(r'^log/$', LogView.as_view(), name='log'),
        url(r'^(?P<env>[-.\w]+)/prompt/$', PromptView.as_view(), name='prompt_env_index'),
        url(r'^(?P<env>[-.\w]+)/prompt/api/$', PromptAPIView.as_view(), name='prompt_env'),
        url(r'^(?P<env>[-.\w]+)/log/$', LogView.as_view(), name='log_env'),
    ]

    if su_settings.DB_PRESET_ENABLED:
        from apistubs.views.settings import SettingsView
        urlpatterns += [
            url(r'^settings/', SettingsView.as_view(), name='settings'),
            url(r'^(?P<env>[-.\w]+)/settings/', SettingsView.as_view(), name='settings_env'),
        ]

    urlpatterns += [
        url(r'^(?P<spec>[-.\w]+)/$', IndexView.as_view(), name='index'),
        url(r'^(?P<spec>[-.\w]+)/api.json$', SpecView.as_view(), name='spec'),
        url(r'^(?P<spec>[-.\w]+)/oauth2-redirect.html$', OAuth2RedirectView.as_view(), name='oauth2_redirect'),
    ]

    urlpatterns += [
        url(r'^(?P<spec>[-.\w]+)/stub/', StubView.as_view(), name='stub'),
        url(r'^(?P<env>[-.\w]+)/(?P<spec>[-.\w]+)/stub/', StubView.as_view(), name='stub_env'),
    ]

    if su_settings.STUB_FORCE_ENABLED:
        from apistubs.openapi.stubforce import StubForceView
        urlpatterns += [
            url(r'^(?P<spec>[-.\w]+)/stubforce/', StubForceView.as_view(), name='stub_force'),
            url(r'^(?P<env>[-.\w]+)/(?P<spec>[-.\w]+)/stubforce/', StubForceView.as_view(), name='stub_force_env'),
        ]
