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
  source /contrib/Modules/3.2.6/init/csh
  module load netcdf/4.1.3_seq
  set parcmp=64
  set machine="bluefire"
  set compiler="ibm"
  set csmdata=/glade/proj3/cseg/inputdata
  set rundata="/ptmp/$USER"
  set netcdf=$NETCDF
  set toolsmake=""
else if (  $host =~ ys* )then
  module load netcdf
  module load ncl
  set parcmp=32
  set machine="yellowstone"
  set compiler="intel"
  set csmdata=/glade/p/cesm/cseg/inputdata
  set rundata="/glade/scratch/$USER"
  set netcdf=$NETCDF
  set toolsmake=""
else if ( $host =~ frankfurt* )then
  set parcmp=2
  set machine="frankfurt"
  set compiler="pgi"
  set csmdata=/fs/cgd/csm/inputdata
  set rundata="/scratch/cluster/$USER"
  set netcdf=/usr/local/netcdf-pgi
  set toolsmake=""
  setenv PATH "${PATH}:/usr/bin"
else if ( $host =~ lynx* )then
  source /opt/modules/default/init/csh
  module load netcdf/4.0.1.3
  set netcdf="$CRAY_NETCDF_DIR/netcdf-pgi"
  set parcmp=12
  set machine="lynx"
  set compiler="pgi"
  set csmdata=/glade/proj3/cseg/inputdata
  set rundata="/glade/scratch/$USER"
  set toolsmake="USER_FC=ftn USER_CC=cc "
else if ( $host =~ yongi* || $host =~ vpn* )then
  set parcmp=12
  set machine="userdefined"
  set compiler="intel"
  set csmdata=/fs/cgd/csm/inputdata
  set rundata="/ptmp/$USER"
  set SCRATCH=$rundata
  set netcdf="/opt/local"
  set toolsmake="USER_FC=ifort USER_LINKER=ifort USER_CC=icc "
  setenv NETCDF_PATH $netcdf
else if ( $host =~ titan* )then

  source /opt/modules/default/init/csh
  module switch pgi       pgi/12.4.0
  module switch xt-mpich2    xt-mpich2/5.4.5
  module switch xt-libsci xt-libsci/11.0.06
  module swap xt-asyncpe xt-asyncpe/5.10
  module load szip/2.1
  module load hdf5/1.8.7
  module load netcdf/4.1.3
  module load parallel-netcdf/1.2.0
  module load esmf/5.2.0rp1
  module load subversion
  set netcdf=$NETCDF_PATH
  set parcmp=9
  set machine="titan"
  set compiler="pgi"
  set csmdata=/tmp/proj/ccsm/inputdata
  set rundata="/tmp/work/$USER"
  set toolsmake="USER_FC=ftn USER_CC=cc "
else
  echo "Bad host to run on: know about bluefire, yellowstone, frankfurt, lynx, yong, and titan"
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
cd $CESM_ROOT/models/lnd/clm/tools/clm4_5/mksurfdata_map/src
if ( $CLM_RETAIN_FILES == FALSE || (! -x mksurfdata_map) )then
   gmake clean
   gmake OPT=TRUE SMP=TRUE -j $parcmp $toolsmake
   if ( $status != 0 ) exit -1
   gmake clean
endif
cd $CESM_ROOT/mapping/gen_domain_files/src
if ( $CLM_RETAIN_FILES == FALSE || (! -x gen_domain) )then
   ../../scripts/ccsm_utils/Machines/configure -mach $machine -compiler $compiler
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
  if ( "$suprted" == "TRUE" ) set compsets = ( ICLM45CN ICLM45 ICLM45 )
  if ( "$suprted" != "TRUE" ) then
     if ( $mysite == "US-UMB" ) then
        set compsets = ( I_1850_CLM45 I20TRCLM45 I20TRCLM45CN ICLM45CN I1850CLM45CN IRCP85CLM45CN ICLM45CN ICLM45CN ICLM45CN )
     else
        set compsets = ( ICLM45 ICLM45 ICLM45 )
     endif
  endif
  set n=0
  foreach compset ( $compsets )
    if ( $compset == ICLM45 ) @ n = $n + 1
    set opt="--caseidprefix=$casedir/$caseprefix"
    set opt="$opt --cesm_root $CESM_ROOT"
    if ( "$suprted" == "TRUE" ) then
      set opt="$opt --nopointdata --stdurbpt --quiet"
    else
      set opt="$opt --owritesrf --run_units=ndays --run_n=5"
    endif
    if ( $compset == I20TRCLM45 || $compset == I20TRCLM45CN || $compset == IRCP85CLM45CN ) set opt="$opt --coldstart"
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
    ./PTCLM.py -d $mycsmdata -m ${machine}_${compiler} -s $mysite -c $compset --rmold $opt
    unset echo
    if ( $status != 0 )then
       echo "FAIL $status" 		>> $statuslog
       if ( "$CLM_SOFF" == "TRUE" ) exit -1
    else
       echo "PASS"         		>> $statuslog
    endif
    cd $case
    ./xmlchange DOUT_S=FALSE
    if ( $status != 0 ) exit -1
    set msg="$casenum $casename.config\t\t\t"
    echo    "$msg"
    echo -n "$msg" >> $statuslog
    ./cesm_setup
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
       ./$casename.build
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
       ./$casename.run
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
    ./$casename.clean_build
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
  set opt="$opt --$spinup --verbose"
  set opt="$opt --cesm_root $CESM_ROOT"
  if ( $finidat != "none" ) set opt="$opt --finidat $finidat"
  echo "Run PTCLM for $casename options = $opt"
  set msg="$casenum $casename.PTCLM\t\t\t"
  echo    "$msg"
  echo -n "$msg" >> $statuslog
  @ casenum = $casenum + 1
  set echo
  ./PTCLM.py -d $mycsmdata -m ${machine}_${compiler} -s $mysite -c $compset --rmold --nopointdata $opt
  unset echo
  if ( $status != 0 )then
      echo "FAIL $status" >> $statuslog
      if ( "$CLM_SOFF" == "TRUE" ) exit -1
  else
      echo "PASS"         >> $statuslog
  endif
  cd $case
  ./xmlchange DOUT_S=FALSE
  if ( $status != 0 ) exit -1
  if ( $spinup == "ad_spinup" || $spinup == "final_spinup" ) then
     set nyrs=2
     ./xmlchange STOP_N=$nyrs,REST_N=$nyrs
     if ( $status != 0 ) exit -1
  endif
  if ( $spinup == "exit_spinup" ) then
     ./xmlchange RUN_TYPE=startup
     if ( $status != 0 ) exit -1
  endif
  set msg="$casenum $casename.config\t\t\t"
  echo    "$msg"
  echo -n "$msg" >> $statuslog
  ./cesm_setup
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
     ./$casename.build
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
     ./$casename.run
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
  ./$casename.clean_build
  cd $pwd
end
set closemsg="Successfully ran all test cases for PTCLM"
echo
echo
echo $closemsg
echo $closemsg >> $statuslog
