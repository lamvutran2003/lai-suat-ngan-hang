from scraper.indexnow import page_hash

PAGE = ('<html><head><title>T</title><meta name="description" content="D"></head><body><header>nav</header>'
        '<section>rates 6,00%</section><footer>views 12</footer><script src="/views.js?v=ab12"></script></body></html>')


def test_footer_and_asset_version_do_not_count_as_changes():
    assert page_hash(PAGE) == page_hash(PAGE.replace("views 12", "views 13").replace("?v=ab12", "?v=cd34"))


def test_content_title_and_description_changes_count():
    assert page_hash(PAGE) != page_hash(PAGE.replace("6,00%", "6,10%"))
    assert page_hash(PAGE) != page_hash(PAGE.replace("<title>T", "<title>T2"))
    assert page_hash(PAGE) != page_hash(PAGE.replace('content="D"', 'content="D2"'))
