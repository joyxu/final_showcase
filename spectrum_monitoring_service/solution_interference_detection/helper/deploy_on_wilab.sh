#!/bin/bash

#rsync -avz  --exclude=.git --exclude '*.o' --exclude '*.h' --exclude '*.c' --exclude '*.pyc' --exclude .repo/ ../../../  -e ssh pgallo@ops:/users/pgallo/wishful-github-manifest-6/
rsync -avz --delete --exclude=examples/interference_recognition/classification --exclude=examples/interference_recognition/station-conf --exclude=examples/interference_recognition/traning_data --exclude=.git --exclude '*.o' --exclude '*.h' --exclude '*.c' --exclude '*.pyc' --exclude .repo/ ../../  -e ssh dgarlisi@ops.wilab2.ilabt.iminds.be:~/wishful-github-manifest-6/
rsync -avz --delete --exclude=.git --exclude '*.o' --exclude '*.h' --exclude '*.c' --exclude '*.pyc' --exclude .repo/ station-conf/reading-tool/  -e ssh dgarlisi@ops.wilab2.ilabt.iminds.be:~/wishful-github-manifest-6/examples/interference_recognition/station-conf/reading-tool/