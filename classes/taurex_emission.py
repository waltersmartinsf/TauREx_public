###########################################################
# TauREx emission execution code.     
###########################################################
#loading libraries     
import pylab,sys,os, logging
import numpy as np #nummerical array library 
import pylab as pl #science and plotting library for python

#loading classes
sys.path.append('./classes')
import emission, output, fitting, atmosphere, data, preselector
from emission import *
from output import *
from fitting import *
from atmosphere import *
from data import *
from preselector import *
import pickle

#loading libraries
sys.path.append('./library')
import library_emission as emlib 


def run(params):

    out_path_orig = params.out_path

    ###############################
    # STAGE 1
    ###############################

    # set output directory of stage 1
    params.out_path = os.path.join(out_path_orig, 'stage_0')

    # initialising data object
    dataob = data(params)

    #initialising TP profile instance
    atmosphereob = atmosphere(dataob)

    #initialising emission radiative transfer code instance
    forwardmodelob = emission(atmosphereob)

    #initialising fitting object
    fittingob = fitting(forwardmodelob)

    #fit data for stage 1
#     if params.downhill_run:
#         fittingob.downhill_fit()    #simplex downhill fit
    fittingob.downhill_fit()    #simplex downhill fit
        
#     if params.mcmc_run and pymc_import:
#         fittingob.mcmc_fit() # MCMC fit
#         MPI.COMM_WORLD.Barrier() # wait for everybody to synchronize here
#         
#     if params.nest_run and multinest_import:
#         fittingob.multinest_fit() # Nested sampling fit   
#         MPI.COMM_WORLD.Barrier() # wait for everybody to synchronize here
           
    
    #generating TP profile covariance from previous fit
    Cov_array = emlib.generate_tp_covariance(fittingob)
    
    
#     pl.figure()
#     pl.imshow(Cov_array,origin='lower')
#     pl.show()
    
        
    #saving covariance 
    np.savetxt(os.path.join(fittingob.dir_stage,'tp_covariance.dat'),Cov_array)
    

    ###############################
    # STAGE 2
    ###############################

    # set output directory of stage 2
    params.out_path = os.path.join(out_path_orig, 'stage_1')

    #setting up objects for stage 2 fitting
    dataob2 = data(params)

    atmosphereob1 = atmosphere(dataob2, tp_profile_type='hybrid', covariance=Cov_array)

    # atmosphereob1.set_TP_hybrid_covmat(Cov_array)

    #setting stage 2 forward model 
    forwardmodelob1 = emission(atmosphereob1)
        
    #setting stage 2 fitting object

    fittingob1 = fitting(forwardmodelob1,stage=1)
    #running stage 2 fit
    if params.downhill_run:
        fittingob1.downhill_fit()    #simplex downhill fit
        
    if params.mcmc_run and pymc_import:
        fittingob1.mcmc_fit() # MCMC fit
        MPI.COMM_WORLD.Barrier() # wait for everybody to synchronize here
        
    if params.nest_run and multinest_import:
        fittingob1.multinest_fit() # Nested sampling fit   
        MPI.COMM_WORLD.Barrier() # wait for everybody to synchronize here
           
    #forcing slave processes to exit at this stage
    if MPIimport and MPI.COMM_WORLD.Get_rank() != 0:
        #MPI.MPI_Finalize()
        exit()
        
    #outputob = output(fittingob)
    outputob1 = output(fittingob1)

    #plotting fits and data
    logging.info('Plotting and saving results')

    #if params.verbose or params.out_save_plots:
        #outputob.plot_all(save2pdf=params.out_save_plots)
        #outputob1.plot_all(save2pdf=params.out_save_plots)
        
    outputob.plot_spectrum()   #plotting data only
    outputob.plot_multinest()  #plotting multinest posteriors
    outputob.plot_mcmc()       #plotting mcmc posterios
    outputob.plot_fit()        #plotting model fits


    outputob.save_ascii_spectra()       #saving models to ascii
    outputob1.save_ascii_spectra()       #saving models to ascii

    # save and plot TP profile (plotting only if save2pdf=True)
    outputob.save_TP_profile(save2pdf=True)  #saving TP profile
    outputob1.save_TP_profile(save2pdf=True)

>>>>>>> feature/transemission
