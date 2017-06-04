#!/usr/bin/python2
# -*- coding: utf-8 -*-

"""Convert markdown to zim wiki syntax.

Stripped and modified from markdown2.py

Syntax converted:

    type             Markdown      ->         Zim
    ----------------------------------------------------
    Heading1         # heading          ===== heading =====
    Heading2         ## heading         ==== heading ====
    Heading3         ### heading        === heading ===
    Heading4         #### heading       == heading ==
    Heading5         ##### heading      = heading =
    Heading6         ###### heading     = heading =
    ----------------------------------------------------
    unordered list   -/+/*              *
    ordered list     1. 2. 3.           1. 2. 3.
    ----------------------------------------------------
    bold             **bold**           **bold**
                     __bold__           __bold__
    italic           *italic*           //italic//
                     _italic_           //italic//
    strike           ~~strike~~         ~~strike~~
    ----------------------------------------------------
    quote            >                  '''
                     texts...           texts...
                                        '''
    code             ```                ```
                     texts...           texts...
                     ```                ```
    ----------------------------------------------------
    inline link      [link](url)        [[url|link]]
    ----------------------------------------------------
    ref link         [link text][id]    
                     [id]:url "title"   [[url|link]]
    ----------------------------------------------------
    inline image     ![img](url)        {{url}}
    ----------------------------------------------------
    ref image        ![img text][id]    
                     [id]:url "title"   {{url}}


Syntax not supported:
    - footnote
    - tables
                     

Update time: 2016-03-21 21:17:19.
"""


import re
import sys,os
import argparse
from lib import tools
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
from random import random, randint

# Use `bytes` for byte strings and `unicode` for unicode strings (str in Py3).
if sys.version_info[0] <= 2:
    py3 = False
    try:
        bytes
    except NameError:
        bytes = str
    base_string_type = basestring
elif sys.version_info[0] >= 3:
    py3 = True
    unicode = str
    base_string_type = str



#---- globals
DEBUG = False

DEFAULT_TAB_WIDTH = 4


SECRET_SALT = bytes(randint(0, 1000000))
def _hash_text(s):
    return 'md5-' + md5(SECRET_SALT + s.encode("utf-8")).hexdigest()



g_escape_table = dict([(ch, _hash_text(ch))
    for ch in '\\`*_{}[]()>#+-.!'])




class Markdown2Zim(object):
    urls = None
    titles = None

    # Used to track when we're inside an ordered or unordered list
    # (see _ProcessListItems() for details):
    list_level = 0

    _ws_only_line_re = re.compile(r"^[ \t]+$", re.M)

    def __init__(self, html4tags=False, tab_width=4):
        self.tab_width = tab_width

        self._outdent_re = re.compile(r'^(\t|[ ]{1,%d})' % tab_width, re.M)
        self._escape_table = g_escape_table.copy()

    def reset(self):
        self.urls = {}
        self.titles = {}
        self.list_level = 0
        self.footnotes = {}
        self.footnote_ids = []


    def convert(self, text):
        """Convert the given text."""
        # Main function. The order in which other subs are called here is
        # essential. Link and image substitutions need to happen before
        # _EscapeSpecialChars(), so that any *'s or _'s in the <a>
        # and <img> tags get encoded.

        # Clear the global hashes. If we don't clear these, you get conflicts
        # from other articles when generating a page which contains more than
        # one article (e.g. an index page that shows the N most recent
        # articles):
        self.reset()

        if not isinstance(text, unicode):
            text = unicode(text, 'utf-8')

        # Standardize line endings:
        text = re.sub("\r\n|\r", "\n", text)

        # Make sure $text ends with a couple of newlines:
        text += "\n\n"

        # Convert all tabs to spaces.
        #text = self._detab(text)

        # Strip any lines consisting only of spaces and tabs.
        # This makes subsequent regexen easier to write, because we can
        # match consecutive blank lines with /\n+/ instead of something
        # contorted like /[ \t]*\n+/ .
        text = self._ws_only_line_re.sub("", text)

        text = self._do_fenced_code_blocks(text)

        # Strip link definitions, store in hashes.
        # Must do footnotes first because an unlucky footnote defn
        # looks like a link defn:
        #   [^4]: this "looks like a link defn"
        text = self._strip_footnote_definitions(text)

        text = self._strip_link_definitions(text)

        #text = self._strip_img_definitions(text)

        text = self._run_block_gamut(text)

        text = self._add_footnotes(text)

        text += "\n"

        return text



    _detab_re = re.compile(r'(.*?)\t', re.M)
    def _detab_sub(self, match):
        g1 = match.group(1)
        return g1 + (' ' * (self.tab_width - len(g1) % self.tab_width))

    def _detab(self, text):
        r"""Remove (leading?) tabs from a file.

            >>> m = Markdown()
            >>> m._detab("\tfoo")
            '    foo'
            >>> m._detab("  \tfoo")
            '    foo'
            >>> m._detab("\t  foo")
            '      foo'
            >>> m._detab("  foo")
            '  foo'
            >>> m._detab("  foo\n\tbar\tblam")
            '  foo\n    bar blam'
        """
        if '\t' not in text:
            return text
        return self._detab_re.subn(self._detab_sub, text)[0]



    def _strip_link_definitions(self, text):
        # Strips link definitions from text, stores the URLs and titles in
        # hash references.
        less_than_tab = self.tab_width - 1

        # Link defs are in the form:
        #   [id]: url "optional title"
        _link_def_re = re.compile(r"""
            ^[ ]{0,%d}\[(.+)\]: # id = \1
              [ \t]*
              \n?               # maybe *one* newline
              [ \t]*
            <?(.+?)>?           # url = \2
              [ \t]*
            (?:
                \n?             # maybe one newline
                [ \t]*
                (?<=\s)         # lookbehind for whitespace
                ['"(]
                ([^\n]*)        # title = \3
                ['")]
                [ \t]*
            )?  # title is optional
            (?:\n+|\Z)
            """ % less_than_tab, re.X | re.M | re.U)
        return _link_def_re.sub(self._extract_link_def_sub, text)


    def _strip_img_definitions(self, text):
        # Strips img definitions from text, stores the URLs and titles in
        # hash references.

        # Link defs are in the form:
        #   ![id]: url "optional title"
        _link_def_re = re.compile(r"""
            ![ ]*\[(.*?)\]     # id = \1
              [ \t]*
            \((.+?)\)           # url = \2
              [ \t]*
            (?:\n+|\Z)
            """, re.X | re.M | re.U | re.S)
        return _link_def_re.sub(self._extract_img_def_sub, text)

    def _extract_img_def_sub(self, match):
        id, url = match.groups()
        key = id.lower()    # Link IDs are case-insensitive
        if key=='':
            key=str(len(self.urls))

        self.urls[key] = self._encode_amps_and_angles(url)
        #if title:
            #self.titles[key] = title
        return ""

    # Ampersand-encoding based entirely on Nat Irons's Amputator MT plugin:
    #   http://bumppo.net/projects/amputator/
    _ampersand_re = re.compile(r'&(?!#?[xX]?(?:[0-9a-fA-F]+|\w+);)')
    _naked_lt_re = re.compile(r'<(?![a-z/?\$!])', re.I)
    _naked_gt_re = re.compile(r'''(?<![a-z0-9?!/'"-])>''', re.I)

    def _encode_amps_and_angles(self, text):
        # Smart processing for ampersands and angle brackets that need
        # to be encoded.
        text = self._ampersand_re.sub('&amp;', text)

        # Encode naked <'s
        text = self._naked_lt_re.sub('&lt;', text)

        # Encode naked >'s
        # Note: Other markdown implementations (e.g. Markdown.pl, PHP
        # Markdown) don't do this.
        text = self._naked_gt_re.sub('&gt;', text)
        return text




    def _extract_link_def_sub(self, match):
        id, url, title = match.groups()
        key = id.lower()    # Link IDs are case-insensitive
        self.urls[key] = self._encode_amps_and_angles(url)
        if title:
            self.titles[key] = title
        return ""


    def _extract_footnote_def_sub(self, match):
        id, text = match.groups()
        text = _dedent(text, skip_first_line=not text.startswith('\n')).strip()
        normed_id = re.sub(r'\W', '-', id)
        # Ensure footnote text ends with a couple newlines (for some
        # block gamut matches).
        self.footnotes[normed_id] = text + "\n\n"
        return ""

    def _strip_footnote_definitions(self, text):
        """A footnote definition looks like this:

            [^note-id]: Text of the note.

                May include one or more indented paragraphs.

        Where,
        - The 'note-id' can be pretty much anything, though typically it
          is the number of the footnote.
        - The first paragraph may start on the next line, like so:

            [^note-id]:
                Text of the note.
        """
        less_than_tab = self.tab_width - 1
        footnote_def_re = re.compile(r'''
            ^[ ]{0,%d}\[\^(.+)\]:   # id = \1
            [ \t]*
            (                       # footnote text = \2
              # First line need not start with the spaces.
              (?:\s*.*\n+)
              (?:
                (?:[ ]{%d} | \t)  # Subsequent lines must be indented.
                .*\n+
              )*
            )
            # Lookahead for non-space at line-start, or end of doc.
            (?:(?=^[ ]{0,%d}\S)|\Z)
            ''' % (less_than_tab, self.tab_width, self.tab_width),
            re.X | re.M)
        return footnote_def_re.sub(self._extract_footnote_def_sub, text)


    def _run_block_gamut(self, text):
        # These are all the transformations that form block-level
        # tags like paragraphs, headers, and list items.

        text = self._do_fenced_code_blocks(text)

        text = self._do_headers(text)

        # Do Horizontal Rules:
        # On the number of spaces in horizontal rules: The spec is fuzzy: "If
        # you wish, you may use spaces between the hyphens or asterisks."
        # Markdown.pl 1.0.1's hr regexes limit the number of spaces between the
        # hr chars to one or two. We'll reproduce that limit here.

        text = self._do_lists(text)

        text = self._do_code_blocks(text)

        text = self._do_block_quotes(text)

        # We already ran _HashHTMLBlocks() before, in Markdown(), but that
        # was to escape raw HTML in the original Markdown source. This time,
        # we're escaping the markup we've just created, so that we don't wrap
        # <p> tags around block-level tags.
        #text = self._hash_html_blocks(text)

        text = self._form_paragraphs(text)

        return text






    def _run_span_gamut(self, text):
        # These are all the transformations that occur *within* block-level
        # tags like paragraphs, headers, and list items.

        text = self._do_code_spans(text)

        text = self._do_links(text)

        text = self._do_strike(text)

        text = self._do_italics_and_bold(text)

        # replace hased symbols like * back to original
        text = self._fill_hased(text)

        # remove some weird unicode chars like '\ufeff'
        text = self._remove_weird(text)

        return text

    def _fill_hased(self,text):
        invertdict=dict(zip(self._escape_table.values(),
            self._escape_table.keys()))
        for kk,vv in invertdict.items():
            text=text.replace(kk,vv)
        return text

    
    _weird_uni_table={u'\ufeff': ''}
    def _remove_weird(self,text):
        for kk,vv in self._weird_uni_table.items():
            text=text.replace(kk,vv)
        return text







    _inline_link_title = re.compile(r'''
            (                   # \1
              [ \t]+
              (['"])            # quote char = \2
              (?P<title>.*?)
              \2
            )?                  # title is optional
          \)$
        ''', re.X | re.S)
    _tail_of_reference_link_re = re.compile(r'''
          # Match tail of: [text][id]
          [ ]?          # one optional space
          (?:\n[ ]*)?   # one optional newline followed by spaces
          \[
            (?P<id>.*?)
          \]
        ''', re.X | re.S)

    _whitespace = re.compile(r'\s*')

    _strip_anglebrackets = re.compile(r'<(.*)>.*')

    def _find_non_whitespace(self, text, start):
        """Returns the index of the first non-whitespace character in text
        after (and including) start
        """
        match = self._whitespace.match(text, start)
        return match.end()

    def _find_balanced(self, text, start, open_c, close_c):
        """Returns the index where the open_c and close_c characters balance
        out - the same number of open_c and close_c are encountered - or the
        end of string if it's reached before the balance point is found.
        """
        i = start
        l = len(text)
        count = 1
        while count > 0 and i < l:
            if text[i] == open_c:
                count += 1
            elif text[i] == close_c:
                count -= 1
            i += 1
        return i

    def _extract_url_and_title(self, text, start):
        """Extracts the url and (optional) title from the tail of a link"""
        # text[start] equals the opening parenthesis
        idx = self._find_non_whitespace(text, start+1)
        if idx == len(text):
            return None, None, None
        end_idx = idx
        has_anglebrackets = text[idx] == "<"
        if has_anglebrackets:
            end_idx = self._find_balanced(text, end_idx+1, "<", ">")
        end_idx = self._find_balanced(text, end_idx, "(", ")")
        match = self._inline_link_title.search(text, idx, end_idx)
        if not match:
            return None, None, None
        url, title = text[idx:match.start()], match.group("title")
        if has_anglebrackets:
            url = self._strip_anglebrackets.sub(r'\1', url)
        return url, title, end_idx




    def _do_links(self, text):
        """Turn Markdown link shortcuts into XHTML <a> and <img> tags.

        This is a combination of Markdown.pl's _DoAnchors() and
        _DoImages(). They are done together because that simplified the
        approach. It was necessary to use a different approach than
        Markdown.pl because of the lack of atomic matching support in
        Python's regex engine used in $g_nested_brackets.
        """
        MAX_LINK_TEXT_SENTINEL = 3000  # markdown2 issue 24

        # `anchor_allowed_pos` is used to support img links inside
        # anchors, but not anchors inside anchors. An anchor's start
        # pos must be `>= anchor_allowed_pos`.
        anchor_allowed_pos = 0

        curr_pos = 0
        while True: # Handle the next link.
            # The next '[' is the start of:
            # - an inline anchor:   [text](url "title")
            # - a reference anchor: [text][id]
            # - an inline img:      ![text](url "title")
            # - a reference img:    ![text][id]
            # - a footnote ref:     [^id]
            #   (Only if 'footnotes' extra enabled)
            # - a footnote defn:    [^id]: ...
            #   (Only if 'footnotes' extra enabled) These have already
            #   been stripped in _strip_footnote_definitions() so no
            #   need to watch for them.
            # - a link definition:  [id]: url "title"
            #   These have already been stripped in
            #   _strip_link_definitions() so no need to watch for them.
            # - not markup:         [...anything else...
            try:
                start_idx = text.index('[', curr_pos)
            except ValueError:
                break
            text_length = len(text)

            # Find the matching closing ']'.
            # Markdown.pl allows *matching* brackets in link text so we
            # will here too. Markdown.pl *doesn't* currently allow
            # matching brackets in img alt text -- we'll differ in that
            # regard.
            bracket_depth = 0
            for p in range(start_idx+1, min(start_idx+MAX_LINK_TEXT_SENTINEL,
                                            text_length)):
                ch = text[p]
                if ch == ']':
                    bracket_depth -= 1
                    if bracket_depth < 0:
                        break
                elif ch == '[':
                    bracket_depth += 1
            else:
                # Closing bracket not found within sentinel length.
                # This isn't markup.
                curr_pos = start_idx + 1
                continue
            link_text = text[start_idx+1:p]

            # Now determine what this is by the remainder.
            p += 1
            if p == text_length:
                return text

            # Inline anchor or img?
            if text[p] == '(': # attempt at perf improvement
                url, title, url_end_idx = self._extract_url_and_title(text, p)
                if url is not None:
                    # Handle an inline anchor or img.
                    is_img = start_idx > 0 and text[start_idx-1] == "!"
                    if is_img:
                        start_idx -= 1

                    # We've got to encode these to avoid conflicting
                    # with italics/bold.
                    url = url.replace('*', self._escape_table['*']) \
                             .replace('_', self._escape_table['_'])
                    if title:
                        title_str = ' title="%s"' % (
                            _xml_escape_attr(title)
                                .replace('*', self._escape_table['*'])
                                .replace('_', self._escape_table['_']))
                        title_str = ''
                    else:
                        title_str = ''
                    if is_img:

                        ########## syntax: image ##############
                        result='{{%s}}' %url
                        ########## syntax: image END ##############

                        curr_pos = start_idx + len(result)
                        text = text[:start_idx] + result + text[url_end_idx:]
                    elif start_idx >= anchor_allowed_pos:

                        ########## syntax: link ##############
                        result_head = '[[%s|' % url
                        result = '%s%s]]' % (result_head, link_text)
                        ########## syntax: link END ##############

                        # <img> allowed from curr_pos on, <a> from
                        # anchor_allowed_pos on.
                        curr_pos = start_idx + len(result_head)
                        anchor_allowed_pos = start_idx + len(result)
                        text = text[:start_idx] + result + text[url_end_idx:]
                    else:
                        # Anchor not allowed here.
                        curr_pos = start_idx + 1
                    continue

            # Reference anchor or img?
            else:
                match = self._tail_of_reference_link_re.match(text, p)
                if match:
                    # Handle a reference-style anchor or img.
                    is_img = start_idx > 0 and text[start_idx-1] == "!"
                    if is_img:
                        start_idx -= 1
                    link_id = match.group("id").lower()
                    if not link_id:
                        link_id = link_text.lower()  # for links like [this][]
                    if link_id in self.urls:
                        url = self.urls[link_id]
                        # We've got to encode these to avoid conflicting
                        # with italics/bold.
                        url = url.replace('*', self._escape_table['*']) \
                                 .replace('_', self._escape_table['_'])
                        title = self.titles.get(link_id)
                        if title:
                            title = _xml_escape_attr(title) \
                                .replace('*', self._escape_table['*']) \
                                .replace('_', self._escape_table['_'])
                            #title_str = ' title="%s"' % title
                            title_str = ''
                        else:
                            title_str = ''
                        if is_img:

                            ########## syntax: image ##############
                            result='{{%s}}' %url
                            ########## syntax: image END ##############

                            curr_pos = start_idx + len(result)
                            text = text[:start_idx] + result + text[match.end():]
                        elif start_idx >= anchor_allowed_pos:

                            ########## syntax: link ##############
                            result_head = '[[%s|' % url
                            result = '%s%s]]' % (result_head, link_text)
                            ########## syntax: link END ##############

                            # <img> allowed from curr_pos on, <a> from
                            # anchor_allowed_pos on.
                            curr_pos = start_idx + len(result_head)
                            anchor_allowed_pos = start_idx + len(result)
                            text = text[:start_idx] + result + text[match.end():]
                        else:
                            # Anchor not allowed here.
                            curr_pos = start_idx + 1
                    else:
                        # This id isn't defined, leave the markup alone.
                        curr_pos = match.end()
                    continue

            # Otherwise, it isn't markup.
            curr_pos = start_idx + 1

        return text





    _h_re_base = r'''
        (^(.+)[ \t]*\n(=+|-+)[ \t]*\n+)
        |
        (^(\#{1,6})  # \1 = string of #'s
        [ \t]%s
        (.+?)       # \2 = Header text
        [ \t]*
        (?<!\\)     # ensure not an escaped trailing '#'
        \#*         # optional closing #'s (not counted)
        \n+
        )
        '''

    _h_re = re.compile(_h_re_base % '*', re.X | re.M)


    def _h_sub(self, match):
        if match.group(1) is not None:
            # Setext header
            n = {"=": 1, "-": 2}[match.group(3)[0]]
            header_group = match.group(2)
        else:
            # atx header
            n = len(match.group(5))
            header_group = match.group(6)

        html = self._run_span_gamut(header_group)

        ########## syntax: headers ##############
        n=max(1,6-n)
        return "%s %s %s\n\n" % ('='*n, html, '='*n)
        ########## syntax: headers END ##############


    def _do_headers(self, text):
        # Setext-style headers:
        #     Header 1
        #     ========
        #
        #     Header 2
        #     --------

        # atx-style headers:
        #   # Header 1
        #   ## Header 2
        #   ## Header 2 with closing hashes ##
        #   ...
        #   ###### Header 6

        return self._h_re.sub(self._h_sub, text)

    _marker_ul_chars  = '*+-'
    _marker_any = r'(?:[%s]|\d+\.)' % _marker_ul_chars
    _marker_ul = '(?:[%s])' % _marker_ul_chars
    _marker_ol = r'(?:\d+\.)'

    def _list_sub(self, match):
        lst = match.group(1)
        #lst_type = match.group(3) in self._marker_ul_chars and "ul" or "ol"
        result = self._process_list_items(lst)
        if self.list_level:

            ########## syntax: list item (ordered) ##############
            return "\n%s\n" % result
        else:
            return "\n%s\n\n" % result
            ########## syntax: list item (ordered) END ##############

    def _do_lists(self, text):
        # Form HTML ordered (numbered) and unordered (bulleted) lists.

        # Iterate over each *non-overlapping* list match.
        pos = 0
        while True:
            # Find the *first* hit for either list style (ul or ol). We
            # match ul and ol separately to avoid adjacent lists of different
            # types running into each other (see issue #16).
            hits = []
            for marker_pat in (self._marker_ul, self._marker_ol):
                less_than_tab = self.tab_width - 1
                whole_list = r'''
                    (                   # \1 = whole list
                      (                 # \2
                        [ ]{0,%d}
                        (%s)            # \3 = first list item marker
                        [ \t]+
                        (?!\ *\3\ )     # '- - - ...' isn't a list. See 'not_quite_a_list' test case.
                      )
                      (?:.+?)
                      (                 # \4
                          \Z
                        |
                          \n{2,}
                          (?=\S)
                          (?!           # Negative lookahead for another list item marker
                            [ \t]*
                            %s[ \t]+
                          )
                      )
                    )
                ''' % (less_than_tab, marker_pat, marker_pat)
                if self.list_level:  # sub-list
                    list_re = re.compile("^"+whole_list, re.X | re.M | re.S)
                else:
                    list_re = re.compile(r"(?:(?<=\n\n)|\A\n?)"+whole_list,
                                         re.X | re.M | re.S)
                match = list_re.search(text, pos)
                if match:
                    hits.append((match.start(), match))
            if not hits:
                break
            hits.sort()
            match = hits[0][1]
            start, end = match.span()
            middle = self._list_sub(match)
            text = text[:start] + middle + text[end:]
            pos = start + len(middle) # start pos for next attempted match

        return text

    _list_item_re = re.compile(r'''
        (\n)?                   # leading line = \1
        (^[ \t]*)               # leading whitespace = \2
        (?P<marker>%s) [ \t]+   # list marker = \3
        ((?:.+?)                # list item text = \4
         (\n{1,2}))             # eols = \5
        (?= \n* (\Z | \2 (?P<next_marker>%s) [ \t]+))
        ''' % (_marker_any, _marker_any),
        re.M | re.X | re.S)

    _last_li_endswith_two_eols = False

    def _list_item_sub(self, match):
        item = match.group(4)
        leading_line = match.group(1)
        if leading_line or "\n\n" in item or self._last_li_endswith_two_eols:
            item = self._run_block_gamut(self._outdent(item))
        else:
            # Recursion for sub-lists:
            item = self._do_lists(self._outdent(item))
            if item.endswith('\n'):
                item = item[:-1]
            item = self._run_span_gamut(item)
        self._last_li_endswith_two_eols = (len(match.group(5)) == 2)

        ########## syntax: list item (unordered) ##############
        bul=match.group(3)
        if bul in self._marker_ul_chars:
            bul=u'*'
        return "%s %s\n" % (bul,item)
        ########## syntax: list item (unordered) END ##############



    def _process_list_items(self, list_str):
        # Process the contents of a single ordered or unordered list,
        # splitting it into individual list items.

        # The $g_list_level global keeps track of when we're inside a list.
        # Each time we enter a list, we increment it; when we leave a list,
        # we decrement. If it's zero, we're not in a list anymore.
        #
        # We do this because when we're not inside a list, we want to treat
        # something like this:
        #
        #       I recommend upgrading to version
        #       8. Oops, now this line is treated
        #       as a sub-list.
        #
        # As a single paragraph, despite the fact that the second line starts
        # with a digit-period-space sequence.
        #
        # Whereas when we're inside a list (or sub-list), that line will be
        # treated as the start of a sub-list. What a kludge, huh? This is
        # an aspect of Markdown's syntax that's hard to parse perfectly
        # without resorting to mind-reading. Perhaps the solution is to
        # change the syntax rules such that sub-lists must start with a
        # starting cardinal number; e.g. "1." or "a.".
        self.list_level += 1
        self._last_li_endswith_two_eols = False
        list_str = list_str.rstrip('\n') + '\n'
        list_str = self._list_item_re.sub(self._list_item_sub, list_str)
        self.list_level -= 1
        return list_str



    def _code_block_sub(self, match, is_fenced_code_block=False):
        if is_fenced_code_block:
            codeblock = match.group(2)
            codeblock = codeblock[:-1]  # drop one trailing newline
        else:
            codeblock = match.group(1)
            codeblock = self._outdent(codeblock)
            codeblock = self._detab(codeblock)
            codeblock = codeblock.lstrip('\n')  # trim leading newlines
            codeblock = codeblock.rstrip()      # trim trailing whitespace

        return "\n\n```%s\n```\n\n" % codeblock




    def _do_code_blocks(self, text):
        return text

    _fenced_code_block_re = re.compile(r'''
        (?:\n\n|\A\n?)
        ^```([\w+-]+)?[ \t]*\n      # opening fence, $1 = optional lang
        (.*?)                       # $2 = code block content
        ^```[ \t]*\n                # closing fence
        ''', re.M | re.X | re.S)

    def _fenced_code_block_sub(self, match):
        return self._code_block_sub(match, is_fenced_code_block=True);

    def _do_fenced_code_blocks(self, text):
        """Process ```-fenced unindented code blocks ('fenced-code-blocks' extra)."""
        return self._fenced_code_block_re.sub(self._fenced_code_block_sub, text)

    # Rules for a code span:
    # - backslash escapes are not interpreted in a code span
    # - to include one or or a run of more backticks the delimiters must
    #   be a longer run of backticks
    # - cannot start or end a code span with a backtick; pad with a
    #   space and that space will be removed in the emitted HTML
    # See `test/tm-cases/escapes.text` for a number of edge-case
    # examples.
    _code_span_re = re.compile(r'''
            (?<!\\)
            (`+)        # \1 = Opening run of `
            (?!`)       # See Note A test/tm-cases/escapes.text
            (.+?)       # \2 = The code block
            (?<!`)
            \1          # Matching closer
            (?!`)
        ''', re.X | re.S)

    '''
    def _code_span_sub(self, match):
        c = match.group(2).strip(" \t")
        c = self._encode_code(c)
        return "<code>%s</code>" % c
    '''

    def _code_span_sub(self, match):
        c = match.group(2).strip(" \t")
        #c = self._encode_code(c)

        ########## syntax: code block ##############
        #return "<code>%s</code>" % c
        codesym=match.group(1)
        if codesym=='```':
            return "%s\n%s\n%s" % (codesym,c,codesym)
        elif codesym=='`':
            return "%s%s%s" % (codesym,c,codesym)
        ########## syntax: code block END ##############

    def _do_code_spans(self, text):
        #   *   Backtick quotes are used for <code></code> spans.
        #
        #   *   You can use multiple backticks as the delimiters if you want to
        #       include literal backticks in the code span. So, this input:
        #
        #         Just type ``foo `bar` baz`` at the prompt.
        #
        #       Will translate to:
        #
        #         <p>Just type <code>foo `bar` baz</code> at the prompt.</p>
        #
        #       There's no arbitrary limit to the number of backticks you
        #       can use as delimters. If you need three consecutive backticks
        #       in your code, use four for delimiters, etc.
        #
        #   *   You can use spaces to get literal backticks at the edges:
        #
        #         ... type `` `bar` `` ...
        #
        #       Turns to:
        #
        #         ... type <code>`bar`</code> ...
        return self._code_span_re.sub(self._code_span_sub, text)

    def _encode_code(self, text):
        """Encode/escape certain characters inside Markdown code runs.
        The point is that in code, these characters are literals,
        and lose their special Markdown meanings.
        """
        replacements = [
            # Encode all ampersands; HTML entities are not
            # entities within a Markdown code span.
            ('&', '&amp;'),
            # Do the angle bracket song and dance:
            ('<', '&lt;'),
            ('>', '&gt;'),
        ]
        for before, after in replacements:
            text = text.replace(before, after)
        hashed = _hash_text(text)
        self._escape_table[text] = hashed
        return hashed

    _strike_re = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.S)
    def _do_strike(self, text):
        text = self._strike_re.sub(r"~~\1~~", text)
        return text

    _strong_re = re.compile(r"(\*\*|__)(?=\S)(.+?[*_]*)(?<=\S)\1", re.S)
    _em_re = re.compile(r"(\*|_)(?=\S)(.+?)(?<=\S)\1", re.S)


    def _do_italics_and_bold(self, text):
        # <strong> must go first:
        ########## syntax: italic and bold ##############
        self._escape_table['**']=_hash_text('**')
        ast_hash=self._escape_table['**']
        #text = self._strong_re.sub(r"**\2**", text)

        # replace ** with a hash
        text = self._strong_re.sub(r"%s\2%s" %(ast_hash, ast_hash), text)
        # do italic
        text = self._em_re.sub(r"//\2//", text)
        # replace hash with **
        text=text.replace(ast_hash,'**')
        ########## syntax: italic and bold END ##############
        return text



    _block_quote_base = r'''
        (                           # Wrap whole match in \1
          (
            ^[ \t]*>%s[ \t]?        # '>' at the start of a line
              .+\n                  # rest of the first line
            (.+\n)*                 # subsequent consecutive lines
            \n*                     # blanks
          )+
        )
    '''
    _block_quote_re = re.compile(_block_quote_base % '', re.M | re.X)
    _block_quote_re_spoiler = re.compile(_block_quote_base % '[ \t]*?!?', re.M | re.X)
    _bq_one_level_re = re.compile('^[ \t]*>[ \t]?', re.M);
    _bq_one_level_re_spoiler = re.compile('^[ \t]*>[ \t]*?![ \t]?', re.M);
    _bq_all_lines_spoilers = re.compile(r'\A(?:^[ \t]*>[ \t]*?!.*[\n\r]*)+\Z', re.M)
    _html_pre_block_re = re.compile(r'(\s*<pre>.+?</pre>)', re.S)
    def _dedent_two_spaces_sub(self, match):
        return re.sub(r'(?m)^  ', '', match.group(1))



    def _block_quote_sub(self, match):
        bq = match.group(1)
        # trim one level of quoting
        bq = self._bq_one_level_re.sub('', bq)
        # trim whitespace-only lines
        bq = self._ws_only_line_re.sub('', bq)
        bq = self._run_block_gamut(bq)          # recurse

        bq = re.sub('(?m)^', '  ', bq)
        # These leading spaces screw with <pre> content, so we need to fix that:
        #bq = self._html_pre_block_re.sub(self._dedent_two_spaces_sub, bq)

        return "'''\n%s\n'''\n\n" % bq




    def _do_block_quotes(self, text):
        if '>' not in text:
            return text
        return self._block_quote_re.sub(self._block_quote_sub, text)

    def _form_paragraphs(self, text):
        # Strip leading and trailing lines:
        text = text.strip('\n')

        # Wrap <p> tags.
        grafs = []
        for i, graf in enumerate(re.split(r"\n{2,}", text)):
            graf = self._run_span_gamut(graf)
            grafs.append(graf.lstrip(" \t"))

        return "\n\n".join(grafs)




    def _add_footnotes(self, text):
        if self.footnotes:
            footer = [
                '<div class="footnotes">',
                '<hr />'
                '<ol>',
            ]
            for i, id in enumerate(self.footnote_ids):
                if i != 0:
                    footer.append('')
                footer.append('<li id="fn-%s">' % id)
                footer.append(self._run_block_gamut(self.footnotes[id]))
                backlink = ('<a href="#fnref-%s" '
                    'class="footnoteBackLink" '
                    'title="Jump back to footnote %d in the text.">'
                    '&#8617;</a>' % (id, i+1))
                if footer[-1].endswith("</p>"):
                    footer[-1] = footer[-1][:-len("</p>")] \
                        + '&#160;' + backlink + "</p>"
                else:
                    footer.append("\n<p>%s</p>" % backlink)
                footer.append('</li>')
            footer.append('</ol>')
            footer.append('</div>')
            return text + '\n\n' + '\n'.join(footer)
        else:
            return text



    def _outdent(self, text):
        # Remove one level of line-leading tabs or spaces
        return text
        #return self._outdent_re.sub('', text)



def _dedent(text, tabsize=8, skip_first_line=False):
    """_dedent(text, tabsize=8, skip_first_line=False) -> dedented text

        "text" is the text to dedent.
        "tabsize" is the tab width to use for indent width calculations.
        "skip_first_line" is a boolean indicating if the first line should
            be skipped for calculating the indent width and for dedenting.
            This is sometimes useful for docstrings and similar.

    textwrap.dedent(s), but don't expand tabs to spaces
    """
    lines = text.splitlines(1)
    _dedentlines(lines, tabsize=tabsize, skip_first_line=skip_first_line)
    return ''.join(lines)

def _xml_escape_attr(attr, skip_single_quote=True):
    """Escape the given string for use in an HTML/XML tag attribute.

    By default this doesn't bother with escaping `'` to `&#39;`, presuming that
    the tag attribute is surrounded by double quotes.
    """
    escaped = (attr
        .replace('&', '&amp;')
        .replace('"', '&quot;')
        .replace('<', '&lt;')
        .replace('>', '&gt;'))
    if not skip_single_quote:
        escaped = escaped.replace("'", "&#39;")
    return escaped


def _dedentlines(lines, tabsize=8, skip_first_line=False):
    """_dedentlines(lines, tabsize=8, skip_first_line=False) -> dedented lines

        "lines" is a list of lines to dedent.
        "tabsize" is the tab width to use for indent width calculations.
        "skip_first_line" is a boolean indicating if the first line should
            be skipped for calculating the indent width and for dedenting.
            This is sometimes useful for docstrings and similar.

    Same as dedent() except operates on a sequence of lines. Note: the
    lines list is modified **in-place**.
    """
    DEBUG = False
    if DEBUG:
        print("dedent: dedent(..., tabsize=%d, skip_first_line=%r)"\
              % (tabsize, skip_first_line))
    margin = None
    for i, line in enumerate(lines):
        if i == 0 and skip_first_line: continue
        indent = 0
        for ch in line:
            if ch == ' ':
                indent += 1
            elif ch == '\t':
                indent += tabsize - (indent % tabsize)
            elif ch in '\r\n':
                continue # skip all-whitespace lines
            else:
                break
        else:
            continue # skip all-whitespace lines
        if DEBUG: print("dedent: indent=%d: %r" % (indent, line))
        if margin is None:
            margin = indent
        else:
            margin = min(margin, indent)
    if DEBUG: print("dedent: margin=%r" % margin)

    if margin is not None and margin > 0:
        for i, line in enumerate(lines):
            if i == 0 and skip_first_line: continue
            removed = 0
            for j, ch in enumerate(line):
                if ch == ' ':
                    removed += 1
                elif ch == '\t':
                    removed += tabsize - (removed % tabsize)
                elif ch in '\r\n':
                    if DEBUG: print("dedent: %r: EOL -> strip up to EOL" % line)
                    lines[i] = lines[i][j:]
                    break
                else:
                    raise ValueError("unexpected non-whitespace char %r in "
                                     "line %r while removing %d-space margin"
                                     % (ch, line, margin))
                if DEBUG:
                    print("dedent: %r: %r -> removed %d/%d"\
                          % (line, ch, removed, margin))
                if removed == margin:
                    lines[i] = lines[i][j+1:]
                    break
                elif removed > margin:
                    lines[i] = ' '*(removed-margin) + lines[i][j+1:]
                    break
            else:
                if removed:
                    lines[i] = lines[i][removed:]
    return lines



        



def main(filein,fileout,verbose=True):

    text=tools.readFile(filein,verbose)
    if verbose:
        print('# <markdown2zim>: Converting to zim...')
    newtext=Markdown2Zim().convert(text)
    tools.saveFile(fileout,newtext,verbose)

    return



#-----------------------Main-----------------------
if __name__=='__main__':


    parser=argparse.ArgumentParser(description=\
            'Convert markdown text to zim wiki syntax.')

    parser.add_argument('file',type=str,\
            help='Input markdown text file.')
    parser.add_argument('-o','--out',type=str,\
            help='Output file name.')
    parser.add_argument('-v','--verbose',action='store_true',\
            default=True)

    try:
        args=parser.parse_args()
    except:
        sys.exit(1)
    
    FILEIN=os.path.abspath(args.file)
    if not args.out:
        FILEOUT='%s_%s.txt' %(os.path.splitext(args.file)[0], 'md2zim')
    else:
        FILEOUT=args.out
    FILEOUT=os.path.abspath(FILEOUT)

    main(FILEIN,FILEOUT,args.verbose)


