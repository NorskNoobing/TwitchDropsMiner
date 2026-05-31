"""Unit tests for webui.html_utils — Tag builder and JS helpers."""

from __future__ import annotations

import json
import re

import pytest

from webui.html_utils import Tag, e, ea, favicon_js, popup_js, close_popup_js, notification_js


class TestTag:
    def test_basic_element(self):
        assert str(Tag("div")) == "<div></div>"

    def test_text_content(self):
        assert str(Tag("span", "hello")) == "<span>hello</span>"

    def test_text_escaping(self):
        assert str(Tag("span", "<script>")) == "<span>&lt;script&gt;</span>"

    def test_classes(self):
        tag = Tag("div").classes("flex gap-2")
        assert 'class="flex gap-2"' in str(tag)

    def test_multiple_class_calls(self):
        tag = Tag("div").classes("flex").classes("gap-2")
        assert 'class="flex gap-2"' in str(tag)

    def test_props(self):
        tag = Tag("img").props(src="/icon.png", loading="lazy")
        assert 'src="/icon.png"' in str(tag)
        assert 'loading="lazy"' in str(tag)

    def test_props_escaping(self):
        tag = Tag("a").props(href='javascript:alert("xss")')
        assert 'javascript:alert(&quot;xss&quot;)' in str(tag)

    def test_trailing_underscore_stripped(self):
        tag = Tag("label").props(for_="my-input")
        assert 'for="my-input"' in str(tag)

    def test_children(self):
        parent = Tag("div").add(Tag("span", "child1"), Tag("span", "child2"))
        html = str(parent)
        assert "<span>child1</span>" in html
        assert "<span>child2</span>" in html

    def test_void_elements(self):
        assert str(Tag("img").props(src="/x.png")) == '<img src="/x.png">'
        assert "</img>" not in str(Tag("img"))

    def test_nested_builder(self):
        html = str(
            Tag("div").classes("flex").add(
                Tag("span", "Hello").classes("text-sm"),
                Tag("img").props(src="/icon.png"),
            )
        )
        assert "flex" in html
        assert "<span" in html
        assert "text-sm" in html
        assert '<img src="/icon.png">' in html


class TestEscaping:
    def test_e_escapes_html(self):
        assert e("<b>") == "&lt;b&gt;"

    def test_e_escapes_amp(self):
        assert e("a&b") == "a&amp;b"

    def test_ea_escapes_quotes(self):
        assert ea('"hello"') == "&quot;hello&quot;"

    def test_e_non_string(self):
        assert e(42) == "42"


class TestFaviconJs:
    def test_icon_name_in_js(self):
        js = favicon_js("active")
        assert "active" in js
        assert ".ico" in js

    def test_icon_name_single_quote_safely_encoded(self):
        name = "test'icon"
        js = favicon_js(name)
        match = re.search(r"'/icons/' \+ (.*?) \+ '.ico'", js)
        assert match is not None
        assert json.loads(match.group(1)) == name

    def test_icon_with_backslash_encoded(self):
        name = r"icon\path"
        js = favicon_js(name)
        match = re.search(r"'/icons/' \+ (.*?) \+ '.ico'", js)
        assert match is not None
        assert json.loads(match.group(1)) == name


class TestPopupJs:
    def test_contains_url(self):
        js = popup_js("https://twitch.tv/activate", "twitch_login")
        assert "twitch.tv" in js
        assert "window.open" in js

    def test_returns_expression(self):
        js = popup_js("https://example.com", "popup")
        assert "!== null" in js

    def test_url_is_json_encoded(self):
        url = "https://example.com/path?q=1&b=2"
        js = popup_js(url, "win")
        match = re.search(r"window\.open\((.*?),", js)
        assert match is not None
        assert json.loads(match.group(1)) == url

    def test_window_name_is_json_encoded(self):
        js = popup_js("https://example.com", "win'name")
        match = re.search(r"window\.open\(.*?,\s*(.*?),", js)
        assert match is not None
        assert json.loads(match.group(1)) == "win'name"


class TestClosePopupJs:
    def test_contains_window_name(self):
        js = close_popup_js("twitch_login")
        assert "twitch_login" in js
        assert ".close()" in js


class TestNotificationJs:
    def test_contains_title_and_message(self):
        js = notification_js("Test Title", "Test Message")
        assert "Test Title" in js
        assert "Test Message" in js
        assert "Notification" in js

    def test_uses_json_encoding(self):
        title = 'He said "hi"'
        message = 'msg with "quotes"'
        js = notification_js(title, message)
        title_match = re.search(r'Notification\((.*?),', js)
        assert title_match is not None
        parsed_title = json.loads(title_match.group(1))
        assert parsed_title == title
