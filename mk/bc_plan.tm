KPL/MK

Meta-kernel for BepiColombo Dataset v310 -- Planning 20220928_001
============================================================================

   This meta-kernel lists the BepiColombo Planning SPICE kernels
   that provide information for the Planning scenario.

   The kernels listed in this meta-kernel and the order in which
   they are listed are picked to provide the best data available and
   the most complete coverage for the BepiColombo Planning scenario.

   This meta-kernel was generated with the Auxiliary Data Conversion
   System version: ADCSng v3.4.2.


Usage of the Meta-kernel
---------------------------------------------------------------------------

   This file is used by the SPICE system as follows: programs that make use
   of this kernel must "load" the kernel normally during program
   initialization. Loading the kernel associates the data items with
   their names in a data structure called the "kernel pool". The SPICELIB
   routine FURNSH loads a kernel into the pool.

   The kernels listed below can be obtained from the ESA SPICE Web server:

      https://spiftp.esac.esa.int/data/SPICE/BEPICOLOMBO/kernels/

   or from the ESA SPICE FTP server:

      ftp://spiftp.esac.esa.int/data/SPICE/BEPICOLOMBO/kernels/


Implementation Notes
---------------------------------------------------------------------------

   It is recommended that users make a local copy of this file and
   modify the value of the PATH_VALUES keyword to point to the actual
   location of the BepiColombo SPICE data set's ``data'' directory on
   their system. Replacing ``/'' with ``\'' and converting line
   terminators to the format native to the user's system may also be
   required if this meta-kernel is to be used on a non-UNIX workstation.


-------------------

   This file was created on September 28, 2022 by Alfredo Escalante Lopez ESA/ESAC.
   The original name of this file was bc_plan_v310_20220928_001.tm.


   \begindata

     PATH_VALUES       = ( '..' )

     PATH_SYMBOLS      = ( 'KERNELS' )

     KERNELS_TO_LOAD   = (

                           '$KERNELS/ck/bc_mpo_magboom_default_s20191107_v01.bc'
                           '$KERNELS/ck/bc_mpo_mga_zero_s20191107_v02.bc'
                           '$KERNELS/ck/bc_mpo_hga_zero_s20191107_v02.bc'
                           '$KERNELS/ck/bc_mpo_sa_zero_s20191107_v02.bc'
                           '$KERNELS/ck/bc_mpo_mertis_zero_s20191107_v02.bc'
                           '$KERNELS/ck/bc_mpo_serena_zero_s20191207_v02.bc'
                           '$KERNELS/ck/bc_mpo_phebus_zero_s20210408_v02.bc'
                           '$KERNELS/ck/bc_mtm_sa_zero_f20181121_v01.bc'
                           '$KERNELS/ck/bc_mmo_sc_scp_20180317_20251220_f20170228_v02.bc'
                           '$KERNELS/ck/bc_mmo_sc_slt_50038_20251220_20280305_f20170228_v02.bc'
                           '$KERNELS/ck/bc_mtm_sc_scp_20180317_20251219_f20181121_v01.bc'
                           '$KERNELS/ck/bc_mtm_sep_scp_20181019_20251205_f20181127_v01.bc'
                           '$KERNELS/ck/bc_mmo_sc_slt_extension_20280305_20300305_f20170228_v02.bc'
                           '$KERNELS/ck/bc_mpo_sc_sct_50041_20181019_20251219_f20181127_v03.bc'
                           '$KERNELS/ck/bc_mpo_sc_prelaunch_f20181121_v01.bc'
                           '$KERNELS/ck/bc_mpo_sc_sct_50034_20251205_20260314_f20181127_v03.bc'
                           '$KERNELS/ck/bc_mpo_sc_slt_50028_20260314_20280529_f20181127_v03.bc'
                           '$KERNELS/ck/bc_mpo_sc_fcp_00130_20181020_20221109_f20181127_v01.bc'

                           '$KERNELS/fk/bc_mpo_v31.tf'
                           '$KERNELS/fk/bc_mtm_v09.tf'
                           '$KERNELS/fk/bc_mmo_v10.tf'
                           '$KERNELS/fk/bc_ops_v01.tf'
                           '$KERNELS/fk/bc_sci_v10.tf'
                           '$KERNELS/fk/bc_dsk_surfaces_v02.tf'
                           '$KERNELS/fk/rssd0004.tf'
                           '$KERNELS/fk/earth_topo_201023.tf'
                           '$KERNELS/fk/earthfixeditrf93.tf'
                           '$KERNELS/fk/estrack_v04.tf'

                           '$KERNELS/ik/bc_mpo_bela_v06.ti'
                           '$KERNELS/ik/bc_mpo_mertis_v07.ti'
                           '$KERNELS/ik/bc_mpo_mgns_v01.ti'
                           '$KERNELS/ik/bc_mpo_mixs_v04.ti'
                           '$KERNELS/ik/bc_mpo_phebus_v05.ti'
                           '$KERNELS/ik/bc_mpo_serena_v07.ti'
                           '$KERNELS/ik/bc_mpo_simbio-sys_v08.ti'
                           '$KERNELS/ik/bc_mpo_sixs_v07.ti'
                           '$KERNELS/ik/bc_mpo_str_v01.ti'
                           '$KERNELS/ik/bc_mpo_aux_v00.ti'
                           '$KERNELS/ik/bc_mtm_mcam_v04.ti'
                           '$KERNELS/ik/bc_mmo_mppe_v02.ti'
                           '$KERNELS/ik/bc_mmo_msasi_v02.ti'
                           '$KERNELS/ik/bc_mmo_ssas_v00.ti'

                           '$KERNELS/lsk/naif0012.tls'

                           '$KERNELS/pck/de403_masses.tpc'
                           '$KERNELS/pck/gm_de431.tpc'
                           '$KERNELS/pck/pck00010.tpc'

                           '$KERNELS/pck/earth_070425_370426_predict.bpc'

                           '$KERNELS/sclk/bc_mpo_step_20220928.tsc'
                           '$KERNELS/sclk/bc_mpo_fict_20181127.tsc'
                           '$KERNELS/sclk/bc_mmo_fict_20170228.tsc'

                           '$KERNELS/spk/de432s.bsp'
                           '$KERNELS/spk/earthstns_itrf93_201023.bsp'
                           '$KERNELS/spk/estrack_v04.bsp'
                           '$KERNELS/spk/bc_sci_v01.bsp'
                           '$KERNELS/spk/bc_mmo_struct_v01.bsp'
                           '$KERNELS/spk/bc_mmo_scp_20181019_20251220_v02.bsp'
                           '$KERNELS/spk/bc_mmo_mlt_50038_20251220_20280305_v05.bsp'
                           '$KERNELS/spk/bc_mmo_slt_extension_20280305_20300305_v01.bsp'
                           '$KERNELS/spk/bc_mtm_struct_v05.bsp'
                           '$KERNELS/spk/bc_mtm_scp_20181019_20251219_v03.bsp'
                           '$KERNELS/spk/bc_mpo_cog_v02.bsp'
                           '$KERNELS/spk/bc_mpo_cog_00130_20181118_20220827_v01.bsp'
                           '$KERNELS/spk/bc_mpo_struct_v07.bsp'
                           '$KERNELS/spk/bc_mpo_schulte_vector_v01.bsp'
                           '$KERNELS/spk/bc_mpo_prelaunch_v01.bsp'
                           '$KERNELS/spk/bc_mpo_mlt_50037_20260314_20280529_v04.bsp'
                           '$KERNELS/spk/bc_mpo_slt_extension_20280529_20300529_v01.bsp'
                           '$KERNELS/spk/bc_mpo_mcp_50041_20181019_20251219_v02.bsp'
                           '$KERNELS/spk/bc_mpo_mcp_50034_20251205_20260314_v03.bsp'
                           '$KERNELS/spk/bc_mpo_fcp_00130_20181020_20251102_v01.bsp'

                         )

   \begintext


SPICE Kernel Dataset Version
--------------------------------------------------------------------------

   The SPICE Kernel Dataset version of the kernels present in this
   meta-kernel is provided by the following keyword (please note that
   this might not be the last version of the SPICE Kernel Dataset):

   \begindata

      SKD_VERSION = 'v310_20220928_001'

   \begintext


Contact Information
--------------------------------------------------------------------------

   If you have any questions regarding this file contact the
   ESA SPICE Service (ESS) at ESAC:

           Alfredo Escalante Lopez
           (+34) 91-8131-429
           spice@sciops.esa.int,


End of MK file.