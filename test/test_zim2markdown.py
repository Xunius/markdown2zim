from __future__ import print_function
from __future__ import unicode_literals
import zim2markdown

text="""
===== heading1 =====

==== heading2 ====

=== heading3 ===

== heading4 ==

= heading5 =

= heading6 =

this is test //**bold test**// of markdown ** ~~parser~~
test.

* item1;
* item2;
* item3.

1. num1;
2. num2;
3. num3.

'''
this is a quote block,
still a quote block,
quote block continues.
quote block continues again.
'''

[[linka]]
[[:linkb]]
[[+linkc]]
[[http:shitshit.com|linkd]]
{{hppt:toimagesite.com}}
{{http:urltoimage.com}}

```
this is a code block,
still a code block,
code block continues.
```
"""

out2=zim2markdown.Zim2Markdown().convert(text)

print(text)
print('\n')
print(out2)
