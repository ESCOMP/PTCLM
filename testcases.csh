#!/bin/csh
#
# testcases.csh
#
# Test the different options to the PTCLM python script.
#
# This goes through most of the different options and cases
# There are a few that are missing however specifically:
#
#     --list, --namelist, --sitegroupname, and --debug
#
# Environment variables to set:
#
# CESM_ROOT:        To test with a separate root to CLM/CESM code set the
#                   env variable CESM_ROOT to the root directory to use.
#
# CLM_SOFF:         If set to TRUE -- stop on first failed test
#
# CLM_RETAIN_FILES: If set to FALSE -- cleanup tools build first
#
# DEBUG:            If set to TRUE -- setup cases, but do not build or run
#

set pwd=`pwd`
set mycsmdata=$HOME/inputdata
set host=`hostname`
set casedir="$pwd/myPTCLMtests.$$"
echo "Run testing for PTCLM.py on $host"

#
# Get path to root
#
if ( ! $?CESM_ROOT )then
   setenv CESM_ROOT "../../../../../.."
endif
if ( ! $?CLM_SOFF )then
   setenv CLM_SOFF "FALSE"
endif
if ( ! $?CLM_RETAIN_FILES )then
   setenv CLM_RETAIN_FILES "TRUE"
endif
if ( ! $?DEBUG )then
   setenv DEBUG "FALSE"
endif
#
# Machine dependent stuff
#
unset SCRATCH
if (      $host =~ be* )then
  set parcmp=64
  set machine="bluefire"
  set csmdata=/fis/cgd/cseg/csm/inputdata
  set rundata="/ptmp/$USER"
  set netcdf=/contrib/netcdf-3.6.2
  set toolsmake=""
else if ( $host =~ mirage*  || $host =~ storm* )then
  set parcmp=8
  set machine="generic_linux_intel"
  set csmdata=/fis/cgd/cseg/csm/inputdata
  set rundata="/ptmp/$USER"
  set SCRATCH=$rundata
  set netcdf=/contrib/netcdf-3.6.2/intel
  set toolsmake="USER_FC=ifort USER_LINKER=ifort "
  setenv NETCDF_PATH $netcdf
else if ( $host =~ edinburgh* )then
  set parcmp=2
  set machine="edinburgh_pgi"
  set csmdata=/fs/cgd/csm/inputdata
  set rundata="/scratch/cluster/$USER"
  set netcdf=/usr/local/netcdf-3.6.3-pgi-hpf-cc-7.2-5
  set toolsmake=""
  setenv PATH "${PATH}:/usr/bin"
else if ( $host =~ lynx* )then
  alias modulecmd /opt/modules/3.1.6.5/bin/modulecmd
  set parcmp=12
  set machine="lynx_pgi"
  set csmdata=/glade/proj3/cseg/inputdata
  set rundata="/ptmp/$USER"
  modulecmd csh load netcdf
  set netcdf="$CRAY_NETCDF_DIR/netcdf-pgi"
  set toolsmake="USER_FC=ftn USER_CC=cc "
else if ( $host =~ yong* )then
  set parcmp=12
  set machine="generic_darwin_intel"
  set csmdata=/fs/cgd/csm/inputdata
  set rundata="/ptmp/$USER"
  set SCRATCH=$rundata
  set netcdf="/usr/local/netcdf-3.6.3-intel-11.1"
  set toolsmake="USER_FC=ifort USER_LINKER=ifort USER_CC=icc "
  setenv NETCDF_PATH $netcdf
else if ( $host =~ jaguar* )then
  set parcmp=9
  set machine="jaguar"
  set csmdata=/tmp/proj/ccsm/inputdata
  set rundata="/tmp/work/$USER"
  module remove netcdf
  module load netcdf/3.6.2
  #set netcdf=$CRAY_NETCDF_DIR/netcdf-pgi   # for netcdf/4
  set netcdf=$NETCDF_DIR
  set toolsmake="USER_FC=ftn USER_CC=cc "
else
  echo "Bad host to run on: know about bluefire, scd data machines, edinburgh, lynx, yong, and jaguar"
  exit -3
endif
setenv INC_NETCDF ${netcdf}/include
setenv LIB_NETCDF ${netcdf}/lib
#
# Create or update the links to my csmdata location
#
echo "Make sure datasets are properly softlinked"
$CESM_ROOT/scripts/link_dirtree $csmdata $mycsmdata
if ( $status != 0 ) exit -1
#
# Build the tools
#
echo "Build the tools"
cd $CESM_ROOT/models/lnd/clm/tools/mksurfdata
if ( $CLM_RETAIN_FILES == FALSE || (! -x mksurfdata) )then
   gmake clean
   gmake OPT=TRUE SMP=TRUE -j $parcmp $toolsmake
   if ( $status != 0 ) exit -1
   gmake clean
endif
cd ../mkgriddata
if ( $CLM_RETAIN_FILES == FALSE || (! -x mkgriddata) )then
   gmake clean
   gmake OPT=TRUE -j $parcmp $toolsmake
   if ( $status != 0 ) exit -1
   gmake clean
endif
cd ../mkdatadomain
if ( $CLM_RETAIN_FILES == FALSE || (! -x mkdatadomain) )then
   gmake clean
   gmake OPT=TRUE -j $parcmp $toolsmake
   if ( $status != 0 ) exit -1
   gmake clean
endif
cd $pwd
#
# Test the different compsets and a couple different sites
# make sure both supported compsets and flux tower sites are used
#
set caseprefix="PTCLM.$$"
set statuslog="tc.$$.status"
@ casenum = 1
echo "Write status info to $statuslog"
cat << EOF  > $statuslog
PTCLM Single-Point Simulation testing Status Log on $host


Testcase                              	          Test Status
EOF
mkdir -p $casedir
foreach mysite ( 1x1_mexicocityMEX US-UMB )
  if ( $mysite == "1x1_mexicocityMEX" || $mysite == "1x1_vancouverCAN" || $mysite == "1x1_brazil" || $mysite == "1x1_urbanc_alpha" ) then
     set suprted=TRUE
  else
     set suprted=FALSE
  endif
  if ( "$suprted" == "TRUE" ) set compsets = ( ICN I I )
  if ( "$suprted" != "TRUE" ) then
     if ( $mysite == "US-UMB" ) then
        set compsets = ( I_1850 I20TR I20TRCN ICN I1850CN IRCP85CN I I I )
     else
        set compsets = ( I I I )
     endif
  endif
  set n=0
  foreach compset ( $compsets )
    if ( $compset == I ) @ n = $n + 1
    set opt="--caseidprefix=$casedir/$caseprefix"
    set opt="$opt --cesm_root $CESM_ROOT"
    if ( $?SCRATCH   )then
        set opt="$opt --scratchroot $SCRATCH"
    endif
    if ( "$suprted" == "TRUE" ) then
      set opt="$opt --nopointdata --ndepgrid --stdurbpt --quiet"
    else
      set opt="$opt --owritesrfaer --run_units=ndays --run_n=5 --aerdepgrid --ndepgrid"
    endif
    if ( $compset == I20TR || $compset == I20TRCN || $compset == IRCP85CN ) set opt="$opt --coldstart"
    set casename="${caseprefix}_${mysite}_${compset}"
    # Use QIAN forcing on second "I" compset
    if ( $n == 2 ) then
      set opt="$opt --useQIAN --QIAN_tower_yrs"
      set casename="${casename}_QIAN"
    endif
    set case = "$casedir/$casename"
    # Use global PFT and SOIL on third
    if ( $n == 3 ) then
      set opt="$opt --pftgrid --soilgrid"
    endif
    \rm -rf $rundata/$casename
    echo "Run PTCLM for $casename options = $opt"
    set msg="$casenum $casename.PTCLM\t\t\t"
    echo    "$msg"
    echo -n "$msg" >> $statuslog
    @ casenum = $casenum + 1
    set echo
    ./PTCLM.py -d $mycsmdata -m $machine -s $mysite -c $compset --rmold $opt
    unset echo
    if ( $status != 0 )then
       echo "FAIL $status" 		>> $statuslog
       if ( "$CLM_SOFF" == "TRUE" ) exit -1
    else
       echo "PASS"         		>> $statuslog
    endif
    cd $case
    ./xmlchange -file env_run.xml -id DOUT_S -val FALSE
    if ( $status != 0 ) exit -1
    set msg="$casenum $casename.config\t\t\t"
    echo    "$msg"
    echo -n "$msg" >> $statuslog
    ./configure -case
    if ( $status != 0 )then
       echo "FAIL $status" 		>> $statuslog
       if ( "$CLM_SOFF" == "TRUE" ) exit -1
    else
       echo "PASS"         		>> $statuslog
    endif
    set msg="$casenum $casename.build\t\t\t"
    echo    "$msg"
    echo -n "$msg" >> $statuslog
    if ( $DEBUG != "TRUE" )then
       ./$casename.$machine.build
    else
       set status=1
    endif
    if ( $status != 0 )then
       echo "FAIL $status" 		>> $statuslog
       if ( "$CLM_SOFF" == "TRUE" ) exit -1
    else
       echo "PASS"         		>> $statuslog
    endif
    set msg="$casenum $casename.run\t\t\t"
    echo    "$msg"
    echo -n "$msg" >> $statuslog
    if ( $DEBUG != "TRUE" )then
       ./$casename.$machine.run
    else
       set status=1
    endif
    if ( $status != 0 )then
       echo "FAIL $status" 		>> $statuslog
       if ( "$CLM_SOFF" == "TRUE" ) exit -1
    else
       echo "PASS"         		>> $statuslog
    endif
    # Clean the build up
    ./$casename.$machine.clean_build
    if ( $compset != I && $n > 1 ) set n = 0
    cd $pwd
  end
end
set mysite=US-UMB
set compset=ICN
set finidat="none"
#
# Now run through the spinup sequence
# (Use the datasets created in the step above)
#
foreach spinup ( ad_spinup exit_spinup final_spinup )
  set casename="${caseprefix}_${mysite}_${compset}_${spinup}"
  set case = "$casedir/$casename"
  set opt="--caseidprefix=$casedir/$caseprefix"
  set opt="$opt --$spinup --verbose --aerdepgrid --ndepgrid"
  set opt="$opt --cesm_root $CESM_ROOT"
  if ( $?SCRATCH   )then
       set opt="$opt --scratchroot $SCRATCH"
  endif
  if ( $finidat != "none" ) set opt="$opt --finidat $finidat"
  echo "Run PTCLM for $casename options = $opt"
  set msg="$casenum $casename.PTCLM\t\t\t"
  echo    "$msg"
  echo -n "$msg" >> $statuslog
  @ casenum = $casenum + 1
  set echo
  ./PTCLM.py -d $mycsmdata -m $machine -s $mysite -c $compset --rmold $opt --nopointdata
  unset echo
  if ( $status != 0 )then
      echo "FAIL $status" >> $statuslog
      if ( "$CLM_SOFF" == "TRUE" ) exit -1
  else
      echo "PASS"         >> $statuslog
  endif
  cd $case
  ./xmlchange -file env_run.xml -id DOUT_S -val FALSE
  if ( $status != 0 ) exit -1
  if ( $spinup == "ad_spinup" || $spinup == "final_spinup" ) then
     set nyrs=2
     ./xmlchange -file env_run.xml -id STOP_N -val $nyrs
     if ( $status != 0 ) exit -1
     ./xmlchange -file env_run.xml -id REST_N -val $nyrs
     if ( $status != 0 ) exit -1
  endif
  if ( $spinup == "exit_spinup" ) then
     ./xmlchange -file env_conf.xml -id RUN_TYPE -val startup
     if ( $status != 0 ) exit -1
  endif
  set msg="$casenum $casename.config\t\t\t"
  echo    "$msg"
  echo -n "$msg" >> $statuslog
  ./configure -case
  if ( $status != 0 )then
      echo "FAIL $status" >> $statuslog
      if ( "$CLM_SOFF" == "TRUE" ) exit -1
  else
      echo "PASS"         >> $statuslog
  endif
  \rm -rf $rundata/$case
  set msg="$casenum $casename.build\t\t\t"
  echo    "$msg"
  echo -n "$msg" >> $statuslog
  if ( $DEBUG != "TRUE" )then
     ./$casename.$machine.build
  else
     set status=1
  endif
  if ( $status != 0 )then
      echo "FAIL $status" >> $statuslog
      if ( "$CLM_SOFF" == "TRUE" ) exit -1
  else
      echo "PASS"         >> $statuslog
  endif
  set msg="$casenum $casename.run\t\t\t"
  echo    "$msg"
  echo -n "$msg" >> $statuslog
  if ( $DEBUG != "TRUE" )then
     ./$casename.$machine.run
  else
     set status=1
  endif
  if ( $status != 0 )then
      echo "FAIL $status" >> $statuslog
      if ( "$CLM_SOFF" == "TRUE" ) exit -1
  else
      echo "PASS"         >> $statuslog
  endif
  if ( $DEBUG != "TRUE" )then
     set finidat=`ls -1 $rundata/$casename/run/$casename.clm?.r.*.nc | tail -1`
  else
     set finidat="$rundata/$casename/run/$casename.clm2.r.0001-01-01-00000.nc"
  endif
  set msg="$casenum $casename.file\t\t\t"
  echo    "$msg"
  echo -n "$msg" >> $statuslog
  if ( $status != 0 )then
      echo "FAIL $status" >> $statuslog
      if ( "$CLM_SOFF" == "TRUE" ) exit -1
  else
      echo "PASS"         >> $statuslog
  endif
  # Clean the build up
  ./$casename.$machine.clean_build
  cd $pwd
end
set closemsg="Successfully ran all test cases for PTCLM"
echo
echo
echo $closemsg
echo $closemsg >> $statuslog
