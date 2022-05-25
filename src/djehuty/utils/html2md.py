"""
Module to check text for html-ness and convert html to markdown.
Works for the limited subset of html from the metadata input form (description)
with elements supported by the UI plus links (sometimes added manually).
There are no nested lists.
The markdown code uses __ for strong/bold and * for em/italic.
"""

import re

def is_html(text):
    #Check if text is html or just plain text
    endtags = ('</p>', '</strong>', '</em>', '</del>', '</sub>', '</sup>',
               '</h2>', '</h3>', '</h4>', '</ul>', '</ol>', '</a>')
    is_html = False
    for endtag in endtags:
        if endtag in text:
            is_html = True
            break
    return is_html

def handle_basic_tags(html):
    markdown = re.sub('\s+', ' ', html).strip()
    replacements = ((' <p><br></p>', '\n'), ('<p><br></p>', '\n'),
                    (' <p>', ''), ('<p>', ''), ('</p>', '\n'),
                    ('<strong>', '__'), ('</strong>', '__'),
                    ('<em>', '*'), ('</em>', '*'),
                    ('<del>', '~~'), ('</del>', '~~'),
                    ('<sub>', '~'), ('</sub>', '~'),
                    ('<sup>', '^'), ('</sup>', '^'),
                    ('<h2>', '\n##'), ('</h2>', '\n'),
                    ('<h3>', '\n###'), ('</h3>', '\n'),
                    ('<h4>', '\n####'), ('</h4>', '\n'))
    for ht, md in replacements:
        markdown = markdown.replace(ht, md)
    return markdown

def handle_lists(html, list_type=None):
    if list_type:
        tag = f'<{list_type}>'
        endtag = f'</{list_type}>'
        split_on_tag = html.split(tag)
        markdown = split_on_tag[0]
        for part in split_on_tag[1:]:
            if endtag in part:
                middle, end = part.split(endtag, 1)
                list_items = handle_list_items(middle)
                if list_type == 'ul':
                    list_text = '\n'.join([f'* {item}' for item in list_items])
                else:
                    list_text = '\n'.join([f'{n+1}. {item}' for n, item in enumerate(list_items)])
                markdown += f'\n{list_text}\n{end}'
    else:
        markdown = handle_lists(handle_lists(html, 'ul'), 'ol')
    return markdown

def handle_list_items(html):
    tag = '<li>'
    endtag = '</li>'
    items=[]
    split_on_tag = html.split(tag)[1:]
    for part in split_on_tag:
        if endtag in part:
            items.append(part.split(endtag, 1)[0])
    return items

def handle_links(html):
    tag = '<a href="'
    endtag = '</a>'
    split_on_tag = html.split(tag)
    markdown = split_on_tag[0]
    for part in split_on_tag[1:]:
        if endtag in part:
            middle, end = part.split(endtag, 1)
            if '"' in  middle:
                url, rest = middle.split('"', 1)
                if '>' in rest:
                    label = rest.split('>', 1)[1]
                    markdown += f'[{label}]({url})'
            markdown += end
    return markdown

def html_to_markdown(html):
    #convert html to markdown
    return handle_links(handle_lists(handle_basic_tags(html)))

def text_to_markdown(text):
    #convert to markdown if input is html, or leave unchanged otherwise.
    return html_to_markdown(text) if is_html(text) else text
