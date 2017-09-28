'''
    TauREx v2 - Development version - DO NOT DISTRIBUTE

    TauREx create spectrum

    Developers: Ingo Waldmann, Marco Rocchetto (University College London)

'''

# loading libraries
import  sys
import os
import argparse
import logging

# loading classes
sys.path.append('./classes')
sys.path.append('./library')

from parameters import *
from transmission import *
from emission import *
from atmosphere import *
from data import *

class create_spectrum(object):

    def __init__(self, params=None, param_filename=None, nthreads=0,full_init=True):

        logging.info('Initialise object create_spectrum')

        if params:
            self.params = params
        elif hasattr(options, 'param_filename'):
            self.params = parameters(options.param_filename,mpi=False)
        elif param_filename:
            self.params = parameters(param_filename, mpi=False)

        if full_init:
            self.init_data()
            self.init_atmosphere(nthreads)
            self.init_fmob()
#         self.dataob = data(self.params)
#         self.atmosphereob = atmosphere(self.dataob, nthreads=nthreads)
#         if self.params.gen_type == 'transmission':
#             self.fmob = transmission(self.atmosphereob)
#         elif self.params.gen_type == 'emission':
#             self.fmob = emission(self.atmosphereob)
            
            
    def init_data(self):
        self.dataob = data(self.params)
        
    def init_atmosphere(self,nthreads):
        self.atmosphereob = atmosphere(self.dataob,nthreads=nthreads)
    
    def init_fmob(self):
        if self.params.gen_type == 'transmission':
            self.fmob = transmission(self.atmosphereob)
        elif self.params.gen_type == 'emission':
            self.fmob = emission(self.atmosphereob)

    def generate_spectrum(self, save_instance=False, instance_filename=None, contrib_func=False, transmittance=False,
                          opacity_contrib=False):

        # this function returns the SPECTRUM_INSTANCE_out dictionary
        # if filename is not specified, store in out_path/SPECTRUM_INSTANCE_out.pickle
        # also stored in self.SPECTRUM_INSTANCE_out

        # create SPECTRUM_out
        instance = {'type': 'create_spectrum',
                 'params': self.params.params_to_dict()}
        instance_data = {}

        # compute spectrum
        instance_data['spectrum'] = np.zeros((self.fmob.atmosphere.int_nwlgrid, 3))
        instance_data['spectrum'][:,0] = self.fmob.atmosphere.int_wlgrid
        instance_data['spectrum'][:,1] = self.fmob.model()

        # freeze the mixing ratio profiles, disable gen_ace
        if self.fmob.params.gen_ace:
            self.fmob.params.gen_ace = False

        # compute contribution function
        if  contrib_func:
            instance_data['contrib_func'] = self.fmob.model(return_tau=True)

        if  transmittance:
            instance_data['transmittance'] = self.fmob.model(return_tau=True)

        # calculate opacity contributions
        if opacity_contrib:
            instance_data['opacity_contrib'] = {}
            active_mixratio_profile = self.fmob.atmosphere.active_mixratio_profile
            atm_rayleigh = self.fmob.params.atm_rayleigh
            atm_cia = self.fmob.params.atm_cia
            atm_clouds = self.fmob.params.atm_clouds
            atm_mie = self.fmob.params.atm_mie

            # opacity from molecules
            for idx, val in enumerate(self.atmosphereob.active_gases):
                mask = np.ones(len(self.atmosphereob.active_gases), dtype=bool)
                mask[idx] = 0
                active_mixratio_profile_mask = np.copy(active_mixratio_profile)
                active_mixratio_profile_mask[mask, :] = 0
                self.fmob.atmosphere.active_mixratio_profile = active_mixratio_profile_mask
                self.fmob.params.atm_rayleigh = False
                self.fmob.params.atm_cia = False
                #self.fmob.params.atm_clouds = False
                instance_data['opacity_contrib'][val] = np.zeros((self.fmob.atmosphere.int_nwlgrid, 2))
                instance_data['opacity_contrib'][val][:,0] = self.fmob.atmosphere.int_wlgrid
                instance_data['opacity_contrib'][val][:,1] = self.fmob.model()
            self.fmob.atmosphere.active_mixratio_profile = np.copy(active_mixratio_profile)

        if opacity_contrib and self.params.gen_type == 'transmission':

            self.fmob.atmosphere.active_mixratio_profile[:, :] = 0

            # opacity from rayleigh
            if atm_rayleigh:
                self.fmob.params.atm_rayleigh = True
                self.fmob.params.atm_cia = False
                self.fmob.params.atm_mie = False
                self.fmob.params.atm_clouds = False
                instance_data['opacity_contrib']['rayleigh'] = np.zeros((self.fmob.atmosphere.int_nwlgrid, 2))
                instance_data['opacity_contrib']['rayleigh'][:,0] = self.fmob.atmosphere.int_wlgrid
                instance_data['opacity_contrib']['rayleigh'][:,1] = self.fmob.model()

            # opacity from cia
            if atm_cia:
                self.fmob.params.atm_rayleigh = False
                self.fmob.params.atm_cia = True
                self.fmob.params.atm_mie = False
                self.fmob.params.atm_clouds = False
                instance_data['opacity_contrib']['cia'] = np.zeros((self.fmob.atmosphere.int_nwlgrid, 2))
                instance_data['opacity_contrib']['cia'][:,0] = self.fmob.atmosphere.int_wlgrid
                instance_data['opacity_contrib']['cia'][:,1] = self.fmob.model()

            # opacity from clouds
            if atm_clouds:
                self.fmob.params.atm_rayleigh = False
                self.fmob.params.atm_cia = False
                self.fmob.params.atm_clouds = True
                self.fmob.params.atm_mie = False
                instance_data['opacity_contrib']['clouds'] = np.zeros((self.fmob.atmosphere.int_nwlgrid, 2))
                instance_data['opacity_contrib']['clouds'][:,0] = self.fmob.atmosphere.int_wlgrid
                instance_data['opacity_contrib']['clouds'][:,1] = self.fmob.model()
            
            #opacity from Mie scattering 
            if atm_mie:
                self.fmob.params.atm_rayleigh = False
                self.fmob.params.atm_cia = False
                self.fmob.params.atm_clouds = False
                self.fmob.params.atm_mie = True
                instance_data['opacity_contrib']['mie'] = np.zeros((self.fmob.atmosphere.int_nwlgrid, 2))
                instance_data['opacity_contrib']['mie'][:,0] = self.fmob.atmosphere.int_wlgrid
                instance_data['opacity_contrib']['mie'][:,1] = self.fmob.model()

            self.fmob.atmosphere.active_mixratio_profile = np.copy(active_mixratio_profile)
            self.fmob.params.atm_rayleigh = atm_rayleigh
            self.fmob.params.atm_cia = atm_cia
            self.fmob.params.atm_clouds = atm_clouds
            self.fmob.params.atm_mie = atm_mie

        # tp profile
        instance_data['temperature_profile'] = np.zeros((self.atmosphereob.nlayers, 2))
        instance_data['temperature_profile'][:,0] = self.fmob.atmosphere.pressure_profile
        instance_data['temperature_profile'][:,1] = self.fmob.atmosphere.temperature_profile

        # altitude
        instance_data['altitude_profile'] = np.zeros((self.atmosphereob.nlayers, 2))
        instance_data['altitude_profile'][:,0] = self.fmob.atmosphere.pressure_profile
        instance_data['altitude_profile'][:,1] = self.fmob.atmosphere.altitude_profile

        # planet_grav
        instance_data['gravity_profile'] = np.zeros((self.atmosphereob.nlayers, 2))
        instance_data['gravity_profile'][:,0] = self.fmob.atmosphere.pressure_profile
        instance_data['gravity_profile'][:,1] = self.fmob.atmosphere.gravity_profile

        # scale_height
        instance_data['scaleheight_profile'] = np.zeros((self.atmosphereob.nlayers, 2))
        instance_data['scaleheight_profile'][:,0] = self.fmob.atmosphere.pressure_profile
        instance_data['scaleheight_profile'][:,1] = self.fmob.atmosphere.scaleheight_profile

        # mu profile
        instance_data['mu_profile'] = np.zeros((self.atmosphereob.nlayers, 2))
        instance_data['mu_profile'][:,0] = self.fmob.atmosphere.pressure_profile
        instance_data['mu_profile'][:,1] = self.fmob.atmosphere.mu_profile

        # mixing ratios
        instance_data['active_mixratio_profile'] = np.zeros((len(self.atmosphereob.active_gases), self.atmosphereob.nlayers, 2))
        instance_data['inactive_mixratio_profile'] = np.zeros((len(self.atmosphereob.inactive_gases), self.atmosphereob.nlayers, 2))
        for i in range(len(self.atmosphereob.active_gases)):
            instance_data['active_mixratio_profile'][i,:,0] = self.fmob.atmosphere.pressure_profile
            instance_data['active_mixratio_profile'][i,:,1] =  self.fmob.atmosphere.active_mixratio_profile[i,:]
        for i in range(len(self.atmosphereob.inactive_gases)):
            instance_data['inactive_mixratio_profile'][i,:,0] = self.fmob.atmosphere.pressure_profile
            instance_data['inactive_mixratio_profile'][i,:,1] =  self.fmob.atmosphere.inactive_mixratio_profile[i,:]


        # store data
        instance['data'] = instance_data

        self.SPECTRUM_INSTANCE_out = instance

        if save_instance:
            if not instance_filename:
                instance_filename = os.path.join(self.params.out_path, 'SPECTRUM_INSTANCE_out.pickle')
            logging.info('Store spectrum instance in %s ' % instance_filename)
            pickle.dump(instance, open(instance_filename, 'wb'), protocol=2)

        return instance

    def save_spectrum(self, sp_filename=None, pickled=False):

        if not hasattr(self, 'SPECTRUM_INSTANCE_out'):
            self.generate_spectrum()

        if not sp_filename:
            if pickled:
                sp_filename = os.path.join(self.params.out_path , 'SPECTRUM_out.pickle')
            else:
                sp_filename = os.path.join(self.params.out_path , 'SPECTRUM_out.dat')
        logging.info('Store spectrum in %s ' % sp_filename)

        if pickled:
            pickle.dump(self.SPECTRUM_INSTANCE_out['data']['spectrum'], open(sp_filename, 'wb'), protocol=2)
        else:
            np.savetxt(sp_filename, self.SPECTRUM_INSTANCE_out['data']['spectrum'])


# gets called when running from command line
if __name__ == '__main__':

    #loading parameter file parser
    parser = argparse.ArgumentParser()

    parser.add_argument('-p',
                      dest='param_filename',
                      default='Parfiles/default.par',
                       help='Input parameter file'
                      )
    # parser.add_argument('--save_sp',       # spectrum is always saved!
    #                   action='store_true',
    #                   dest='save_sp',
    #                   default=True)

    parser.add_argument('--pickle', # store spectrum in its pickled version (faster for highres spectra)
                      action='store_true',
                      dest='pickle_save_sp',
                      default=False,
                       help='Store the final output spectrum in Python pickle format. This is much faster for high resolution '
                            'spectra than using ascii files. See also --sp_filename.')

    parser.add_argument('--sp_filename',
                      dest='sp_filename',
                      default=False,
                      help='Specify a custom file path and filename for the output spectrum (note that the path is relative'
                           'to the current working folder). Remember that if using --pickle_save_sp the ouput spectrum '
                           'is stored in Python pickle format.')

    parser.add_argument('--save_instance',
                      action='store_true',
                      dest='save_instance',
                      default=False,
                      help = 'Save a dictionary in .pickle format containing the full spectrum instance, including mixing ratio and ' \
                             'temperature profiles used, and all the paramaters used to generate the spectrum.'
                             'See also the options --opacity__contriv, --contrib_func. Default file path is in the'
                             'Output folder specified in parameter file, and the default filename is '
                             'SPECTRUM_INSTANCE_out.pickle. Otherwise see --instance_filename')

    parser.add_argument('--instance_filename',
                      dest='instance_filename',
                      default=False,
                      help = 'Specify a custom file path and filename for the output spectrum instance dictionary (stored'
                             'in Python pickle format.')

    # default to true
    # parser.add_argument('--opacity_contrib',  # calculates the opacity contribution for each opacity source.
    #                   dest='opacity_contrib', # stored in SPECTRUM_INSTANCE_out.pickle, so use '--save_instance' as well
    #                   action='store_true',
    #                   default=False,
    #                   help = 'Calculates the opacity contribution for each opacity source. It computes one spectrum for '
    #                          'each opacity source, suppressing the contribution from all the other sources. Stored in the instance'
    #                          'dictionary (see option --save_instance) under ["data"]["opacity_contrib"][<opacity_source>]')

    parser.add_argument('--contrib_func',
                      dest='contrib_func',
                      action='store_true',
                      default=False,
                      help = 'Only valid for emission. Store the contribution function as a funciton of pressure and wavelength.'
                             'The 2d array is stored in the instance dictionary (see option --save_instance), '
                             'under ["data"]["contrib_func"].',)

    parser.add_argument('--transmittance',
                      dest='transmittance',
                      action='store_true',
                      default=False,
                      help = 'Only valid for transmission. Store the spectral transmittance as a function of pressure'
                             ' as a funciton of pressure and wavelength. The transmittance is integrated over the path '
                             'parallel to the line of sight. The 2d array is stored in the instance dictionary (see option --save_instance), '
                             'under ["data"]["transmittance"].',)

    parser.add_argument('--nthreads',  # run forward model in multithreaded mode (use Python multiprocesing for sigma array interpolation
                       dest='nthreads', # and openmp parallel version of cpp code). You need to spcify the number of cores to use,
                       default=0,
                       type=int,
                       help = 'Run forward model in multithreaded mode (using NTHREADS cores). NTHREADS should not '
                              'be larger than the number of cores available.')

    # plotting parameters
    parser.add_argument('--plot',
                      dest='plot_spectrum',
                      action='store_true',
                      default=False,
                      help='Display an instantanous plot after the spectrum is computed.')

    parser.add_argument('--save_plots',
                      dest='save_plots',
                      action='store_true',
                      default=False,
                      help='Save a range of plots in the Output folder specified.')

    parser.add_argument('--plot_profiles',
                        action='store_true',
                        dest='plot_profiles',
                        default=False)

    parser.add_argument('--plot_resolution',
                        dest='plot_resolution',
                        default=100,
                        help='Output plot spectrum resolution. Set to 0 for native resolution.')

    parser.add_argument('--plot_contrib',
                        action='store_true',
                        dest='plot_contrib',
                        default=False,
                        help='Plot the contribution of each molecule to the spectrum')

    parser.add_argument('--plot_title',
                        dest='plot_title',
                        default=False)

    parser.add_argument('--plot_prefix',
                        dest='plot_prefix',
                        default=False)

    parser.add_argument('--plot_out_folder',
                        dest='plot_out_folder',
                        default=False)

    # add command line interface to parameter file

    params_tmp = parameters(mpi=False, log=False)
    params_dict = params_tmp.params_to_dict() # get all param names
    for param in params_dict:
        if type(params_dict[param]) == list:
            # manage lists
            parser.add_argument('--%s' % param,
                                action='append',
                                dest=param,
                                default=None,
                                type = type(params_dict[param][0])
                                )
        else:
            parser.add_argument('--%s' % param,
                                dest=param,
                                default=None,
                                type = type(params_dict[param])
                                )
    options = parser.parse_args()

    # Initialise parameters instance
    params = parameters(options.param_filename, mode='forward_model', mpi=False)

    # Override params object from command line input
    for param in params_dict:
        if getattr(options, param) != None:

            value = getattr(options, param)
            if param == 'planet_mass':
                value *= MJUP
            if param == 'planet_radius':
                value *= RJUP
            if param == 'star_radius':
                value *= RSOL
            if param == 'atm_mu':
                value *= AMU
            setattr(params, param, value)

    # checks
    if params.gen_type == 'transmission' and options.contrib_func:
        logging.error('Options --contrib_func is only valid in emission. Maybe you wanted to use --transmittance? ')

    if params.gen_type == 'emission' and options.transmittance:
        logging.error('Options --transmittance is only valid in transmission. Maybe you wanted to use --contrib_func ?')

    if (options.transmittance or options.contrib_func) and not options.save_instance:
        logging.warning('Options --transmittance and --contrib_func require --save_instance. This options is '
                        'switched on automatically. The instance of the spectrum will be stored in a .pickle file'
                        'in the Output folder.')
        options.save_instance = True

    spectrumob = create_spectrum(params=params, nthreads=options.nthreads)

    sp_instance = spectrumob.generate_spectrum(save_instance=options.save_instance,
                                                 instance_filename=options.instance_filename,
                                                 opacity_contrib=True,
                                                 contrib_func=options.contrib_func,
                                                 transmittance=options.transmittance)

    spectrumob.save_spectrum(sp_filename=options.sp_filename, pickled=options.pickle_save_sp)

    # plotting
    if options.save_plots:
        sys.path.append('./tools')
        from taurex_plots import taurex_plots

        logging.info('Initialising plotting')
        plot = taurex_plots(plot_type='create_spectrum',pickle_file=sp_instance, title=options.plot_title,
                            prefix=options.plot_prefix, out_folder=options.plot_out_folder,
                            plot_resolution=options.plot_resolution)

        # plot spectrum
        plot.plot_forward_spectrum(plot_contrib=options.plot_contrib)

        # plot mixing ratio profiles
        if options.plot_profiles:
            plot.plot_forward_xp()

            # do plot transmissivity contrib funct


    if options.plot_spectrum:
        logging.info('Plot spectrum... Close the Plot window to terminate the script.')
        sp = spectrumob.SPECTRUM_INSTANCE_out['data']['spectrum']
        plt.plot(sp[:,0], sp[:,1])
        plt.xscale('log')
        plt.show()