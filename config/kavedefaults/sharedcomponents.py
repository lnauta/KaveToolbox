#!/usr/bin/env python
##############################################################################
#
# Copyright 2016 KPMG Advisory N.V. (unless otherwise stated)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
##############################################################################
"""
shared components are the KaveToolbox itself and java
anything used by more than one package installation lives here
"""
import os
import kaveinstall as li
from kaveinstall import Component, linuxVersion


# top level directory under where to keep all KAVE software
li.InstallTopDir = "/opt"

# ######################  KAVETOOLBOX ITSELF ############################


class Toolbox(Component):
    """
    Wrapper class for overwriting certain parts of the default installer
    """
    oldvdetect = False

    def clean(self, others_only=False):
        """
        Special case of clean script, don't clean my own directory if this script is running *from* there!
        """
        # first case, clean before or after, and everything is OK
        if self.cleanBefore and (not os.path.dirname(__file__).startswith(self.installDir)):
            return super(Toolbox, self).clean(others_only)
        # second case, I'm in the right directory, so OK so long as others_only is true
        if self.cleanBefore and os.path.realpath(os.path.dirname(__file__)).startswith(self.installDirVersion):
            super(Toolbox, self).clean(True)
        # third case, any other cleanBefore combi is a definite no go
        # The other two if statements will mostly aways activate before we get here
        if self.cleanBefore:
            self.cleanBefore = False
            self.cleanAfter = True
            return False
        return super(Toolbox, self).clean(others_only)

    def installfrom(self):
        minstallfrom = os.path.realpath(os.sep.join(__file__.split(os.sep)[:-2]))
        if minstallfrom == "":
            minstallfrom = ".."
        if minstallfrom.endswith("scripts"):
            minstallfrom = minstallfrom[:-len("scripts")]
        if minstallfrom.endswith("config"):
            minstallfrom = minstallfrom[:-len("config")]
        return minstallfrom

    def oldvwarning(self):
        print "WARNING:-----------------------------------------------------"
        print "WARNING: an existing 1.X version of KaveToolbox was detected."
        print "WARNING: lots of packages will be skipped, to really update."
        print "WARNING: please add --clean-before or see the readme/wiki !."
        print "WARNING:-----------------------------------------------------"
        self.oldvdetect = True

    def envscript(self):
        guess_installed = self.installDirVersion + os.sep + "scripts" + os.sep + "KaveEnv.sh"
        if os.path.exists(guess_installed):
            return guess_installed + " " + self.version
        guess_pro = self.installDirPro + os.sep + "scripts" + os.sep + "KaveEnv.sh"
        if os.path.exists(guess_pro):
            return guess_pro
        guess_old = self.installDir + os.sep + "scripts" + os.sep + "KaveEnv.sh"
        if os.path.exists(guess_old):
            if not self.oldvdetect:
                self.oldvwarning()
            return guess_old
        installfrom = self.installfrom()
        return installfrom + os.sep + "scripts" + os.sep + "KaveEnv.sh"

    def buildenv(self):
        prepend = False
        rest = []
        scriptloc = self.envscript().split()[0]
        # recreate env script in case it totally does not exist, or somehow is missing the intro...
        if not os.path.exists(scriptloc) and os.path.exists(self.installDirVersion + '/scripts/'):
            prepend = True
        elif os.path.exists(scriptloc):
            f = open(scriptloc)
            rest = f.readlines()
            f.close()
            if not len(rest) > 1:
                prepend = True
            elif not rest[0].startswith("#!/bin/bash"):
                prepend = True
        if prepend and os.path.exists(os.path.dirname(scriptloc)):
            f = open(scriptloc, 'w')
            f.write("""#!/bin/bash

# Simple script to set up the KAVE environment
# called automatically from /etc/profile.d if the installer has
# been run.

# touch ~/.nokaveEnv to disable the automatic calling of the script

# touch .kaveEnv to force automatic calling of the script unless .nokaveEnv is present

# touch ~/.nokaveBanner to disable printing the banner

"""
                    )
            f.write(''.join(rest))
            f.close()
        return super(Toolbox, self).buildenv()

    def script(self):
        # don't include the .git directory
        if ".git" in self.installfrom():
            raise NameError(
                "Sorry, I cannot be installed from a directory which includes '.git' in the name! Can you please "
                "download/copy to a different directory and try again")
        if os.path.realpath(self.installfrom()) != os.path.realpath(self.installDirVersion):
            self.run(
                "rsync -rv --exclude=.git --exclude=.project --exclude=.pydevproject --exclude=.pyc "
                + self.installfrom()
                + "/ " + self.installDirVersion)
        # self.run("mv ./"+self.installfrom().rstrip('/').split('/')[-1]+" "+self.installDir)
        f = open(self.installfrom() + os.sep + "scripts" + os.sep + "autoKaveEnv.sh")
        l = f.read()
        f.close()
        l = l.replace("%ENVSCRIPT%", self.installDirPro + '/scripts/KaveEnv.sh')
        # overwrite if it exists
        if not os.access("/etc/profile.d", os.W_OK):
            self.bauk(
                "cannot write into /etc/profile.d, this means you are not running with root privilages. "
                "Run again as root, or turn off the explicit toolbox.doInstall in kaveconfiguration.py")
        f = open("/etc/profile.d/kave.sh", "w")
        f.write(l)
        f.close()
        # add to bash.bashrc for non-interactive&non-login shells
        l = "#!/bin/bash\n"
        if os.path.exists("/etc/bash.bashrc"):
            f = open("/etc/bash.bashrc")
            l = f.read()
            f.close()
        if "/etc/profile.d/kave.sh" not in l:
            f = open("/etc/bash.bashrc", "w")
            if not len(l.strip()):
                l = "#!/bin/bash"
            f.write(l)
            f.write("""
if [ -e /etc/profile.d/kave.sh ]; then
    source /etc/profile.d/kave.sh
fi
""")
            f.close()
        # set default wallpaper on workstations
        if (self.setwallpaper is True or (self.kind == 'workstation'
                                          and self.setwallpaper in ['default', 'workstation'])):
            if linuxVersion.lower().startswith("centos6"):
                self.run('gconftool-2 --direct --config-source xml:readwrite:/etc/gconf/gconf.xml.defaults '
                         + '--type string --set /desktop/gnome/background/picture_filename '
                         + self.installDirPro + '/figs/KAVE_wp' + str(self.wallpaperselect) + '.png')
                self.run('gconftool-2 --direct --config-source xml:readwrite:/etc/gconf/gconf.xml.defaults '
                         + ' --type string --set /desktop/gnome/background/picture_options centered')
            else:
                cfpath = '/etc/xdg/xfce4/xfconf/xfce-perchannel-xml'
                template = 'xfce4-desktop.xml'
                if linuxVersion.lower().startswith("centos7"):
                    cfpath = '/etc/dconf/db/local.d'
                    template = '00-background'
                if not os.path.exists(cfpath):
                    os.makedirs(cfpath, 0755)
                self.run('cp -f '
                         + os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), template)
                         + ' ' + cfpath)
                self.run('sed -i "s/%%INSTALLDIRPRO%%/'
                         + self.installDirPro.replace('/', '\\/')
                         + '/g"  ' + os.path.join(cfpath, template))
                self.run('sed -i "s/%%WPNUM%%/' + str(self.wallpaperselect) + '/g"  ' + os.path.join(cfpath, template))
                if linuxVersion.lower().startswith("centos7"):
                    self.run('dconf update')
        return True


toolbox = Toolbox("KaveToolbox")
toolbox.doInstall = True
toolbox.installSubDir = "KaveToolbox"
toolbox.freespace = 100
toolbox.usrspace = 200
toolbox.tempspace = 100
toolbox.workstationExtras = {"Centos6": ['yum -y groupinstall "Desktop" "Desktop Platform" '
                                         '"X Window System" "Fonts" --exclude=NetworkManager\\*',
                                         # --exclude=pulseaudio\\* --skip-broken',
                                         'yum -y install tigervnc-server firefox xpdf'],
                             "Centos7": ['yum -y groupinstall "Desktop"  "GNOME Desktop" '
                                         '"Desktop Platform" "X Window System" "Fonts"',
                                         # --exclude=NetworkManager\\* --exclude=pulseaudio\\* --skip-broken',
                                         'yum -y install tigervnc-server firefox pixman pixman-devel libXfont xpdf'],
                             "Ubuntu": ['apt-get -y install firefox xpdf',
                                        'if dpkg -l xserver-xorg-input-mouse 2>/dev/null > /dev/null ;'
                                        + ' then true; else '  # Only install x if x not installed
                                        + 'apt-get -y install xfce4 xfce4-goodies;'
                                        + 'fi;',
                                        'apt-get -y install tightvncserver'
                                        ]
                             }
toolbox.setwallpaper = 'default'  # wallpaper if it is a workstation type
toolbox.wallpaperselect = 0  # a number between 0 and 9
toolbox.pre = {"Centos6": ["yum -y install vim emacs wget curl zip unzip tar gzip rsync git"],
               "Centos7": ["yum -y install vim emacs wget curl zip unzip tar gzip rsync git"],
               "Ubuntu": ['apt-get -y install dictionaries-common',
                          "apt-get -y install vim emacs wget curl zip unzip tar gzip rsync git"]
               }
toolbox.register_toolbox(toolbox)
toolbox.env = """

ktbv='%%VERSION%%'
pro='yes'

# Choose the versioning to use
# No arguments -- use all pro versioning
# X : use fixed versioning from version X install

if [ -n "$1" ]; then
   if [ ${ktbv} == "$1" ]; then
     pro='no'
   elif [ "$1" == 'pro' ]; then
     pro='yes'
   elif [ -d %%INSTALLDIR%%/${1} ]; then
     source %%INSTALLDIR%%/${1}/scripts/KaveEnv.sh $1
     exit 0
   fi
fi

if [ ${pro} == 'yes' ]; then
    export KAVETOOLBOX=%%INSTALLDIRPRO%%
else
    export KAVETOOLBOX=%%INSTALLDIRVERSION%%
fi

# Allow mixed 1.X/2.X versions
if [ ! -d ${KAVETOOLBOX} ]; then
  export KAVETOOLBOX="%%INSTALLDIR%%"
fi

ban='yes'
if [ $TERM != "dumb" ]; then
    if [ ! -z "$HOME" ]; then
        if [ -d "$HOME" ]; then
            if [ -e  "$HOME"/.nokaveBanner ]; then
                ban='no'
            fi
        fi
    fi
    if [ ${ban} == 'yes' ]; then
        if [ -e ${KAVETOOLBOX}/Welcome.banner ]; then
            cat ${KAVETOOLBOX}/Welcome.banner
        fi
    fi
fi


#only add directories to path if they are not already there!
if [[ ":$PATH:" == *":$KAVETOOLBOX/bin:$KAVETOOLBOX/scripts:"* ]]; then
    true
else
    export PATH=$KAVETOOLBOX"/bin:"$KAVETOOLBOX"/scripts:"${PATH}
fi

if [[ ":$PYTHONPATH:" == *":$KAVETOOLBOX/python:"* ]]; then
    true
else
    export PYTHONPATH=$KAVETOOLBOX"/python:"${PYTHONPATH}
fi

#Add spark if spark is installed
if type pyspark >/dev/null 2>/dev/null; then
  export SPARK_HOME=`readlink -f \`which pyspark\``
  export SPARK_HOME=`dirname \`dirname $SPARK_HOME\``
  if [[ ":$PYTHONPATH:" == *":$SPARK_HOME/python:"* ]]; then
    true
  else
    export PYTHONPATH=${SPARK_HOME}"/python:"${PYTHONPATH}
  fi
fi

"""
toolbox.tests = [('source $KAVETOOLBOX/scripts/KaveEnv.sh > /dev/null', 0, '', ''),
                 ("python -c \"import correlograms; import geomaps; import stattools; import rootnotes;\"", 0, '', '')]

# ### JAVA component ####

java = Component("java")
java.version = '1.8'
java.usrspace = 175
java.pre = {"Centos6": ["yum -y install java-1.8.0-openjdk java-1.8.0-openjdk-devel"],
            "Centos7": ["yum -y install java-1.8.0-openjdk java-1.8.0-openjdk-devel"],
            "Ubuntu": ["add-apt-repository ppa:openjdk-r/ppa -y",
                       "apt-get update",
                       "apt-get -y install openjdk-8-jre openjdk-8-jdk openjdk-8-source "]
            }
java.post = {"Centos6": ["bash -c 'IFS=\";\" read -r jdir string <<< `ls -dt /usr/lib/jvm/java-1.8*-openjdk*`;"
                         " export jdir; "
                         "alternatives --install /usr/bin/java java ${jdir}/jre/bin/java 20000; "
                         "if [ -e ${jdir}/bin/javac ]; then alternatives "
                         "--install /usr/bin/javac javac ${jdir}/bin/javac 20000; fi ;"
                         "if [ -e ${jdir}/jre/bin/javaws ]; then alternatives "
                         "--install /usr/bin/javaws javaws ${jdir}/jre/bin/javaws 20000; fi; "
                         "alternatives --set java ${jdir}/jre/bin/java; "
                         "if [ -e ${jdir}/bin/javac ]; then alternatives --set javac ${jdir}/bin/javac; fi; "
                         "if [ -e ${jdir}/jre/bin/javaws ]; then alternatives "
                         "--set javaws ${jdir}/jre/bin/javaws; fi; '"
                         ]
             }
java.post["Centos7"] = java.post["Centos6"]
java.post["Ubuntu"] = [c.replace("alternatives", "update-alternatives") for c in java.post["Centos6"]]

# ##### all ############

__all__ = ['toolbox', 'java']
