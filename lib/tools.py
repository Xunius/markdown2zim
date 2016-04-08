'''
Utility functions.

Update time: 2016-03-24 11:11:46.
'''
import os
import re



def deu(text):
    if isinstance(text,str):
        return text.decode('utf8','replace')
    else:
        return text

def enu(text):
    if isinstance(text,unicode):
        return text.encode('utf8','replace')
    else:
        return text



#-------------------Read in text file and store data-------------------
def readFile(abpath_in,verbose=True):
    '''Read in text file and store data

    <abpath_in>: str, absolute path to input txt.
    '''

    abpath_in=expandUser(abpath_in)

    if not os.path.exists(abpath_in):
        raise Exception("\n# <readFile>: Input file not found.")

    if verbose:
        print('\n# <readFile>: Open input file:')
        print(abpath_in)
        print('\n# <readFile>: Reading lines...')
        
    lines=[]

    with open(abpath_in, 'r') as fin:
        for line in fin:
            lines.append(deu(line))
    lines=u''.join(lines)

    if verbose:
        print('# <readFile>: Got all data.')

    return lines




def autoRename(abpath):
    '''Auto rename a file to avoid overwriting an existing file

    <abpath>: str, absolute path to a folder or a file to rename.
    
    Return <newname>: str, renamed file path, by appending "_(n)".
    E.g. 
        n1='~/codes/tools/send2ever.py'
        n2='~/codes/tools/send2ever_(4).py'
    will be renamed to
        n1='~/codes/tools/send2ever_(1).py'
        n2='~/codes/tools/send2ever_(5).py'
    '''

    if not os.path.exists(abpath):
        return expandUser(abpath)

    def rename_sub(match):
        base=match.group(1)
        delim=match.group(2)
        num=int(match.group(3))
        return '%s%s(%d)' %(base,delim,num+1)

    folder,filename=os.path.split(abpath)
    basename,ext=os.path.splitext(filename)
    # match filename
    rename_re=re.compile('''
            ^(.+?)       # File name
            ([- _])      # delimiter between file name and number
            \\((\\d+)\\) # number in ()
            $''',\
            re.X)
    if rename_re.match(basename):
        newname=rename_re.sub(rename_sub,basename)
        newname='%s%s' %(newname,ext)
    else:
        newname='%s_(1)%s' %(basename,ext)

    newname=os.path.join(folder,newname)
    newname=expandUser(newname)

    return newname



#---------------Save result to file---------------
def saveFile(abpath_out,text,overwrite=True,verbose=True):

    abpath_out=expandUser(abpath_out)
    if os.path.isfile(abpath_out):
        if overwrite:
            os.remove(abpath_out)
        else:
            abpath_out=autoRename(abpath_out)

    if verbose:
        print('\n# <saveFile>: Saving result to:')
        print(abpath_out)

    with open(abpath_out, mode='a') as fout:
        fout.write(enu(text))

    return
        

        

#------------------Expand user home "~" in file names------------------
def expandUser(path,verbose=True):
    '''Expand user home "~" in file names

    '''
    if type(path) is list or type(path) is tuple:
        filelist=[os.path.expanduser(ii) for ii in path]
        return filelist

    elif type(path) is str:
        return os.path.expanduser(path)



