import shutil
import sys

from configparser import RawConfigParser
from hashlib import md5
from os import listdir, mkdir, remove, system, walk
from os.path import abspath, exists, join, split
from time import sleep, time

VERSION = 100

# For these folders (key), parse these types (comma-separated)
BASE_EXT = {"Animations":"ukx",
            "KarmaData":"ka",
            "Maps":"ut2",
            "Sounds":"uax",
            "StaticMeshes":"usx",
            "System":"u,ucl",
            "Textures":"utx"}

NAME = "RedirectBuilder"

DEFAULT_CFG = {NAME:{"verbosity":"3",
                     "con-update":"1.0",
                     "temp":"temp",
                     "batch-size":"20"}}


# some functions I borrowed from the old redirect building script

def fmove(target, dir_, verbose=False):
    """Move a file target into directory dir_"""
##    if not dir_.endswith("\\"): dir_ += "\\"
    fn = split(target)[1]
    if not fn: fn = target # !!!!!!
    try: shutil.move(target, dir_)
    except:
        if verbose:
            print("Failed to move `%s` directly, attempting to delete it..." % \
                  fn, file=sys.stderr)
            print(sys.exc_info())
        try:
            remove(join(dir_, fn))
            shutil.move(target, dir_)
        except: print("Failed to move `%s`!" % fn, file=sys.stderr)

def fcopy(target, dir_, verbose=False):
    """Copy a file target into directory dir_"""
    if not dir_.endswith("\\"): dir_ += "\\"
    fn = target.rpartition("\\")[2]
    if not fn: fn = target # !!!!!!
    try: shutil.copy(target, dir_)
    except:
        if verbose:
            print("Failed to copy `%s` directly, attempting to delete it..." % \
                  fn, file=sys.stderr)
        try:
            remove(dir_+fn)
            shutil.copy(target, dir_)
        except: print("Failed to copy `%s`!" % fn, file=sys.stderr)

# new stuff, these are a bit hacky

def wffstcu(dir_, expfc, fail=10.):
    """Wait for filesystem to catch up"""
    t = time()
    while len(listdir(dir_)) < expfc:
        sleep(0.25)
        if t + fail < time(): break

def wfdcdtcu(dir_, should_exist, fail=10.):
    """Wait for directory creation/destruction to catch up"""
    t = time()
    while exists(dir_) != should_exist:
        sleep(0.25)
        if t + fail < time(): break

class RedirectBuilder(object):
    """Used to initialize the md5 banlist so we don't re-parse stock files"""
    def __init__(self, cfg_fn="config.ini"):
##    def __init__(self, bd, blf="md5ban.csv", con=3, upd_int=1):
        self.valid = False
        cp = RawConfigParser()
        cp.read_dict(DEFAULT_CFG)
        try: cp.read(cfg_fn)
        except:
            if self.con >= 1:
                print("Could not load the configuration!",
                      file=sys.stderr)
                return
        self.con = int(DEFAULT_CFG[NAME]["verbosity"])
        try:
            self.bds = cp[NAME]["build-banlist-from"] # banlist data source
        except KeyError: # if this key is absent, use existing banlist file
            self.bds = None
        try:
            self.upd_int = float(cp[NAME]["con-update"]) # console update intvl
            self.con = int(cp[NAME]["verbosity"]) # verbosity level 0-4
            self.tmp = cp[NAME]["temp"] # temp folder path for ucc
            self.blf = cp[NAME]["banlist"] # banlist file name
            self.rds = cp[NAME]["data-source"] # redirect data source
            self.ucc = cp[NAME]["ucc"] # path to the ucc executable to use
            self.out = cp[NAME]["output-folder"] # uz2 destination folder
            self.bs = int(cp[NAME]["batch-size"]) # num. files for ucc compress
        except KeyError:
            if self.con >= 1:
                print("Could not load an incomplete configuration",
                      file=sys.stderr)
                return
        except ValueError:
            if self.con >= 1:
                print("Could not parse all values in the configuration",
                      file=sys.stderr)
                return
        # cleanup for easier computing
        self.tmp = abspath(self.tmp)
        self.rds = abspath(self.rds)
        self.blf = abspath(self.blf)
        self.ucc = abspath(self.ucc)
        if self.bds and not exists(self.blf):
            self.create_banlist()
        self.check_hash = exists(self.blf)
        if not exists(self.out):
            mkdir(self.out)
        # determine which paths we want to walk through
        self.bl_wanted_paths = [join(self.bds, p) for p in BASE_EXT.keys()]
        self.rd_wanted_paths = [join(self.rds, p) for p in BASE_EXT.keys()]
        self.valid = True

    def __bool__(self):
        return self.valid

    def create_banlist(self):
        if self.con >= 1: print("Creating banlist hashes...")
        with open(self.blf, "w"): pass
        for r, d, f in walk(self.bds):
            if r in self.bl_wanted_paths:
                tslu = time() # time since last update
                if self.con >= 4: print((r, d, f))
                files_done = 0
                cd = r.rpartition('\\')[2]
                if self.con >= 2: print("%s has %d files to compute" % (cd,
                                                                        len(f)))
                with open(self.blf, "a") as of:
                    for fn in f:
                        if fn.rpartition('.')[2] in \
                           BASE_EXT[cd].split(','):
                            with open(join(r, fn), 'rb') as d:
                                m = md5()
                                m.update(d.read())
                                l = "%s,%s" % (fn, m.hexdigest())
                                of.write(l+"\n")
                                if self.con >= 4: print(l)
                            del l, m
                            files_done += 1
                            if tslu + self.upd_int < time() and self.con >= 2:
                                print("%s: %d of %d files done" % (cd,
                                                                   files_done,
                                                                   len(f)))
                                tslu = time()
        if self.con >= 1: print("MD5 banlist created.")

    def check_md5_ban(self, fn):
        """Check if file is in the MD5 ban list"""
        try:
            with open(self.blf, 'r'): pass
        except IOError:
            return None # no ban list, no conclusive result
        m = md5()
        with open(fn, "rb") as f:
            m.update(f.read())
        h = m.hexdigest()
        del m
        with open(self.blf, 'r') as blf:
            for l in blf:
                if l.rpartition(',')[2].strip() == h: return True
        return False

    def check_name_ban(self, fn):
        """Check if file is in the name ban list"""
        try:
            with open(self.blf, 'r'): pass
        except IOError:
            return None # no ban list, no conclusive result
        with open(self.blf, 'r') as blf:
            for l in blf:
                if l.rpartition(',')[0].strip() == fn: return True
        return False

    def create_tmp(self):
        """Create the temp folder."""
        try: mkdir(self.tmp)
        except FileExistsError:
            self.delete_tmp()
            mkdir(self.tmp)
        wfdcdtcu(self.tmp, True)

    def delete_tmp(self):
        """Delete the temp folder."""
        shutil.rmtree(self.tmp)
        wfdcdtcu(self.tmp, False)

    def clean_compressed(self):
        fnl = list(map(lambda r:join(self.tmp, r),
                       filter(lambda q:q.endswith(".uz2"), listdir(self.tmp))))
        for fn in fnl: remove(fn)
        return len(fnl)

    def move_compressed(self, dst):
        fnl = list(map(lambda r:join(self.tmp, r),
                       filter(lambda q:q.endswith(".uz2"), listdir(self.tmp))))
        for fn in fnl: fmove(fn, dst, (self.con >= 4))
        return len(fnl)

    def compress_files(self, fnl):
        """Send filename list through UCC and move output to output folder"""
        self.create_tmp()
        self.clean_compressed()
        for fn in fnl: # bring files into temp folder
            fcopy(fn, self.tmp, (self.con >= 4))
        wffstcu(self.tmp, len(fnl))
        sleep(1.5)
        system(self.ucc+" compress "+join(self.tmp,"*"))
        wffstcu(self.tmp, len(fnl)*2)
        self.move_compressed(self.out)
        # delete temp after verifying data moved out

    def do_compress(self):
        if self.con >= 1: print("Beginning compression...")
        ftc = [] # files to compress
        # this is stored separately because we'll only do up to x files at once
        for r, d, f in walk(self.rds):
            if r in self.rd_wanted_paths:
                tslu = time() # time since last update
                if self.con >= 4: print((r, d, f))
                files_done = 0
                cd = r.rpartition('\\')[2]
                if self.con >= 2: print("%s has %d files to catalogue" % \
                                        (cd, len(f)))
                for fn in f:
                    fn = join(r, fn)
                    if fn.rpartition('.')[2] in BASE_EXT[cd].split(','):
                        if self.check_hash:
                            if self.check_md5_ban(fn):
                                files_done += 1
                                continue
                            ftc.append(fn)
                            files_done += 1
                            if tslu + self.upd_int < time() and self.con >= 2:
                                print("%s: %d of %d files catalogued" % \
                                      (cd, files_done, len(f)))
                                tslu = time()
        if self.con >= 2: print("%d files need to be compressed." % len(ftc))
        to_compress = []
        sl = len(ftc) # starting length, since we destroy ftc next
        mfc = 0 # moved file count
        while True:
            try: to_compress.append(ftc.pop())
            except IndexError:
                if not to_compress: break
            if not ftc or len(to_compress) >= self.bs:
                if self.con >= 2: print("%d of %d compressed!" % \
                                        (sl-len(ftc), sl))
                self.compress_files(to_compress)
                mfc += len(to_compress)
                wffstcu(self.out, mfc)
                self.delete_tmp()
                to_compress = []
        if self.con >= 1: print("Files compressed!")


def main(argv):
    global m
    if len(argv) > 1:  m = RedirectBuilder(argv[1])
    else:
        print("UT2003/2004 Redirect Builder v%d.%02d" % (int(VERSION/100),
                                                         (VERSION % 100)))
        print("Syntax: python "+split(argv[0])[1]+" config-file")
        return
    if not m:
        print("Failed to load the redirect builder!")
        return
    m.do_compress()

if __name__ == "__main__":
    main(sys.argv)
