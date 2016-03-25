# markdown2zim

Convert between **markdown** and **zim wiki** syntax

## What does this do?

Convert a text file written in **markdown** or **zim wiki** to the other.

## Syntax table:

```
    ----------------------------------------------------
    type             Markdown       <->         Zim
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
    quote            > texts...         '''
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
```



Links in **zim** are translated to file paths, e.g. `[[+linktonote]]` is converted
to `[linktonote](~/path_to_current_file/title_of_current_note/linktonote.txt)`

Similary image links are converted to file paths.


## Syntax not supported:

    - footnote
    - tables


The core functionality is stripped and modified from **markdown2**.



## Usage

### **markdown** to **zim**:

```
python markdown2zim.py input [-o output]
```


### **zim** to **markdown**:

```
python zim2markdown.py input [-o output]
```

where `-o output` is the output file, default to "input_md2zim.txt" or "input_zim2md.md"







