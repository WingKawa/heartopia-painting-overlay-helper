from html.parser import HTMLParser
from pathlib import Path
from PIL import Image


def test_guide_is_self_contained_and_all_images_exist():
    guide = Path(__file__).resolve().parents[1]/'docs'/'guide'/'index.html'
    class Resources(HTMLParser):
        def __init__(self):
            super().__init__()
            self.images = []
            self.sections = []
            self.links = []
            self.ids = set()
        def handle_starttag(self,tag,attrs):
            attrs = dict(attrs)
            if 'id' in attrs:
                self.ids.add(attrs['id'])
            if tag=='a' and attrs.get('href','').startswith('#'):
                self.links.append(attrs['href'][1:])
            if tag=='img':
                assert attrs.get('alt')
                self.images.append(attrs['src'])
            if tag=='section':
                self.sections.append(attrs.get('id'))
            if tag=='script':
                assert 'src' not in attrs
    parser = Resources()
    parser.feed(guide.read_text(encoding='utf-8'))
    assert parser.sections==[f'step-{index}' for index in range(1,6)]+['image-conversion','troubleshooting','rules-and-privacy']
    assert all(link in parser.ids for link in parser.links)
    assert len(set(parser.images))==8
    for source in parser.images:
        assert '://' not in source and not source.startswith('/')
        with Image.open(guide.parent/source) as image:
            image.verify()
