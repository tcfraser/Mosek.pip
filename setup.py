# NOTE to whoever happens to look in this file: I had to cheat a bit
# to get the installer to work with PIP. Since the 'build' action
# effectively builds both python source and binary libraries (by
# downloading and unpacking the binary distribution)

import setuptools.command.install
import setuptools.command.egg_info
import distutils.command.build
from   setuptools import setup
import platform,sys
import os,os.path
import shutil

class VersionError(Exception): pass
class URLError(Exception): pass

with open(os.path.join(os.path.dirname('__file__'),'PKG-INFO'),'rt') as f:
    for l in f:
        if l.startswith('Version:'):
            mosekver = l[len('Version:'):].strip().split('.')
            break

mosekmajorver = mosekver[0]
mosekminorver =  mosekver[1]

######################
# Platform setup
######################


major,minor,_,_,_ = sys.version_info
if (major != 2 or minor < 5) and (major != 3 or minor < 3):
    print("Python 2.5+ required, got %d.%d" % (major,minor))

import ctypes
is_64bits = 8 == ctypes.sizeof(ctypes.c_void_p) # figure out if python is 32bit or 64bit
pf        = platform.system()

if   pf == 'Windows':
    if is_64bits:
        pfname = "win64x86"
        pkgname = 'mosektoolswin64x86.zip'
        moseklibs = [ 'mosek64_{0}_{1}.dll'.format(mosekmajorver,mosekminorver),
                      'mosekxx{0}_{1}.dll'.format(mosekmajorver,mosekminorver),
                      'libiomp5md.dll',
                      'mosekscopt{0}_{1}.dll'.format(mosekmajorver,mosekminorver) ]
    else:
        pfname = "win32x86"
        pkgname = 'mosektoolswin32x86.zip'
        moseklibs = [ 'mosek{0}_{1}.dll'.format(mosekmajorver,mosekminorver),
                      'mosekxx{0}_{1}.dll'.format(mosekmajorver,mosekminorver),
                      'libiomp5md.dll',
                      'mosekscopt{0}_{1}.dll'.format(mosekmajorver,mosekminorver) ]
    dldir = os.environ.get('TEMP')
elif pf == 'Linux':
    if is_64bits:
        pfname = "linux64x86"
        pkgname = 'mosektoolslinux64x86.tar.bz2'
        moseklibs = [ 'libmosek64.so.{0}.{1}'.format(mosekmajorver,mosekminorver),
                      'libiomp5.so',
                      'libmosekxx{0}_{1}.so'.format(mosekmajorver,mosekminorver),
                      'libmosekscopt{0}_{1}.so'.format(mosekmajorver,mosekminorver)]
    else:
        pfname = "linux32x86"
        pkgname = 'mosektoolslinux32x86.tar.bz2'
        moseklibs = [ 'libmosek.so.{0}.{1}'.format(mosekmajorver,mosekminorver),
                      'libiomp5.so',
                      'libmosekxx{0}_{1}.so'.format(mosekmajorver,mosekminorver),
                      'libmosekscopt{0}_{1}.so'.format(mosekmajorver,mosekminorver)]
    dldir = '{0}/Downloads'.format(os.environ['HOME']) # appears to be standart
elif pf == 'Darwin':
    pfname = "osx64x86"
    pkgname = 'mosektoolsosx64x86.tar.bz2'
    dldir = '{0}/Downloads'.format(os.environ['HOME'])
    moseklibs = [ 'libmosek64.{0}.{1}.dylib'.format(mosekmajorver,mosekminorver),
                  'libiomp5.dylib',
                  'libmosekxx{0}_{1}.dylib'.format(mosekmajorver,mosekminorver),
                  'libmosekscopt{0}_{1}.dylib'.format(mosekmajorver,mosekminorver) ]
else:
    raise VersionError("Unsupported platform {0}".format(pf))

if dldir is not None and not os.path.isdir(dldir):
    dldir = None

pkgpath     = '/stable/{0}.{1}.0.{2}/{3}'.format(mosekver[0],mosekver[1],mosekver[2],pkgname)
unpackdir   = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)),'src'))
distroplatformpfx = 'mosek/{0}/tools/platform/{1}'.format(mosekmajorver,pfname)

######################
# Get mosek package
######################

def _pre_install():
    """
    Fetch MOSEK distribution and unpack the python module structure
    """
    # Download the newest distro
    if dldir is not None:
        pkgfilename = os.path.join(dldir,'Mosek-{0}.{1}.{2}-'.format(*mosekver)+pkgname)
    else: # download to local directory
        pkgfilename = os.path.join(unpackdir,pkgname)

    if not os.path.exists(pkgfilename):
        try:
            # python 2
            import httplib
        except ImportError:
            # python 3
            import http.client as httplib

        c = httplib.HTTPConnection('download.mosek.com')
        try:
            url = "http://download.mosek.com"+pkgpath

            c.request('GET',pkgpath)
            r = c.getresponse()
            if r.status != 200:
                raise URLError("Failed to fetch MOSEK package '{0}'. Response {1} ({2})".format(url,r.status,r.reason))
            with open(pkgfilename,"wb") as f:
                shutil.copyfileobj(r,f)
        finally:
            c.close()

    licensepdf = 'mosek/{0}/license.pdf'.format(mosekmajorver)
    pypfx = '{0}/python/{1}/mosek'.format(distroplatformpfx,major)

    if os.path.splitext(pkgname)[-1] == '.zip':
        import zipfile
        with zipfile.ZipFile(pkgfilename) as zf:
            for tmem in zf.infolist():
                if tmem.filename.startswith(pypfx):
                    zf.extract(tmem,os.path.dirname(tmem.filename[len(pypfx):]))
                elif os.path.basename(tmem.filename) in moseklibs:
                    zf.extract(tmem,unpackdir)
                elif tmem.filename == licensepdf:
                    zf.extract(tmem,unpackdir)
    else:
        import tarfile

        with tarfile.open(pkgfilename) as tf:
            for tmem in tf:
                if (tmem.isfile() and (tmem.name.startswith(pypfx))) or \
                   os.path.basename(tmem.name) in moseklibs or \
                   tmem.name == licensepdf:
                    tf.extract(tmem,unpackdir)

def _post_install(sitedir):
    """
    Unpack and install the necessary binary libraries and the
    license. Create the mosekorigin module.
    """
    tgtpath = os.path.join(sitedir,'mosek',pfname)
    try: os.makedirs(tgtpath)
    except OSError: pass

    libsrcdir = os.path.join(unpackdir,'mosek',mosekmajorver,'tools','platform',pfname,'bin')
    for l in moseklibs:
        shutil.copyfile(os.path.join(libsrcdir,l),os.path.join(tgtpath,l))

    with open(os.path.join(sitedir,'mosek','mosekorigin.py'),'wt') as f:
        f.write('__mosekinstpath__ = """{0}"""\n'.format(os.path.join(sitedir,'mosek')))

    # Copy python modules
    try:
        shutil.rmtree(os.path.join(sitedir,'mosek'))
    except:
        pass
    shutil.copytree(os.path.join('src','mosek',mosekmajorver,'tools','platform',pfname,'python',str(major),'mosek'),
                    os.path.join(sitedir,'mosek'))
    shutil.copy(os.path.join('src','mosek',mosekmajorver,'license.pdf'),
                os.path.join(sitedir,'mosek'))
    print("""
*** MOSEK for Python ***
Please read through the MOSEK software license before using MOSEK:
     {0}
To use MOSEK for optimization a license file is required. Free
academic licenses, commercial trial licenses and full licenses can be
obtained at http://mosek.com.
""".format(os.path.join(sitedir,'mosek','license.pdf')))

class build(distutils.command.build.build):
    def run(self):
        self.execute(_pre_install,(), msg="Fetch and unpack MOSEK distro")
        distutils.command.build.build.run(self)

class install(setuptools.command.install.install):
    def run(self):
        setuptools.command.install.install.run(self)
        self.execute(_post_install,
                     (self.install_lib,),
                     msg="Install binary libraries")

packages = [ 'mosek','mosek.fusion' ]

setup( name='Mosek',
       cmdclass     = { 'build'   : build,
                        'install' : install },
       version      = '{0}.{1}.{2}'.format(mosekmajorver,mosekminorver,mosekver[2]),
       #packages     = packages,
       #package_dir  = { 'mosek'        : os.path.join('src','mosek',mosekmajorver,'tools','platform',pfname,'python',str(major),'mosek') },
       install_requires = ['numpy>=1.4' ],
       author       = 'Mosek ApS',
       author_email = "support@mosek.com",
       description  = 'Mosek/Python APIs',
       long_description = 'Interface for MOSEK',
       license      = "See license.pdf in the MOSEK distribution",
       url          = 'http://www.mosek.com',
       )
