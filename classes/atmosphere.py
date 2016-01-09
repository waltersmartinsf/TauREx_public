'''
    TauREx v2 - Development version - DO NOT DISTRIBUTE

    Atmosphere class

    Developers: Ingo Waldmann, Marco Rocchetto (University College London)

'''

#loading libraries
import numpy as np
import scipy.special as spe
import logging
import sys
import matplotlib.pylab as plt

from library_constants import *
from library_general import *

class atmosphere(object):

    def __init__(self, data, params=None, tp_profile_type=None, covariance=None):

        logging.info('Initialising atmosphere object')

        # set some objects and variables
        if params is not None:
            self.params = params
        else:
            self.params = data.params

        self.data = data
        self.fit_transmission = self.params.fit_transmission
        self.fit_emission = self.params.fit_emission

        # active and inactive gas names and mixing ratios
        self.nallgases = len(self.params.atm_active_gases) + len(self.params.atm_inactive_gases)
        self.nactivegases = len(self.params.atm_active_gases)
        self.ninactivegases = len(self.params.atm_inactive_gases)

        # set planet radius, mass, gravity
        self.planet_radius = self.params.planet_radius
        self.planet_mass = self.params.planet_mass
        self.planet_grav = self.get_surface_gravity() # this should be set as a function of altitude


        self.max_pressure = self.params.atm_max_pres

        self.nlayers = self.params.atm_nlayers # todo change for external ATM file

        # set mixing ratios profiles of active and inactive gases. todo optionally convert to single value profiles?
        self.active_mixratio_profile = np.zeros(( self.nactivegases, self.nlayers))
        self.inactive_mixratio_profile = np.zeros((self.ninactivegases, self.nlayers))
        for i in xrange(self.nactivegases):
            self.active_mixratio_profile[i, :] = self.params.atm_active_gases_mixratios[i]
        for i in xrange(self.ninactivegases):
            self.inactive_mixratio_profile[i, :] = self.params.atm_inactive_gases_mixratios[i]

        if self.params.atm_couple_mu:
            self.planet_mu = self.get_coupled_planet_mu()
        else:
            self.planet_mu = np.zeros((self.nlayers))
            self.planet_mu[:] = self.params.planet_mu

        logging.info('Planet radius: %.3f RJUP' % (self.planet_radius/RJUP))
        logging.info('Planet mass: %.3f MJUP' % (self.planet_mass/MJUP))
        logging.info('Planet gravity (log g): %.3f cgs' % (np.log10(self.planet_grav)))
        logging.info('Mean molecular weight: %.5f AMU' % (self.planet_mu[0]/AMU))
        logging.info('Atmospheric max pressure: %.3f bar' % (self.max_pressure/1e5))

        # set pressure profile. This is fixed
        self.pressure_profile = self.get_pressure_profile()

        # set initial temperature profile. todo optionally convert to single value?
        self.temperature_profile = np.zeros((self.nlayers))
        self.temperature_profile[:] = self.params.planet_temp

        # set initial altitude grid. This will vary during fitting as planet_mu, planet_temp vary
        self.scale_height = self.get_scale_height()
        self.altitude_profile = self.get_altitude_profile()

        # set density profile
        self.density_profile = self.get_density_profile()

        # set cloud parameters # todo improve cloud model
        if self.params.atm_clouds:
            self.clouds_lower_P = self.params.atm_cld_lower_P
            self.clouds_upper_P = self.params.atm_cld_upper_P
            self.clouds_m = self.params.atm_cld_m
            self.clouds_a = self.params.atm_cld_a

        # selecting TP profile to use
        if tp_profile_type is None:
            self.TP_type = self.params.atm_tp_type
        else:
            self.TP_type = tp_profile_type

        # setting up TP profile
        self.set_TP_profile()

        # set non-linear sampling grid for hybrid model
        if tp_profile_type == 'hybrid':
            self.hybrid_covmat = covariance
            self.get_TP_sample_grid(covariance, delta=0.05)

        # get sigma array (and interpolate sigma array to pressure profile)
        self.sigma_array = self.get_sigma_array()
        self.sigma_array_flat = self.sigma_array.flatten()

        # get sigma rayleigh array (for active and inactive absorbers)
        self.sigma_rayleigh_array = self.get_sigma_rayleigh_array()
        self.sigma_rayleigh_array_flat = self.sigma_rayleigh_array.flatten()

        # get collision induced absorption cross sections
        self.sigma_cia_array = self.get_sigma_cia_array()
        self.sigma_cia_array_flat = self.sigma_cia_array.flatten()
        self.cia_idx = self.get_cia_idx()

        logging.info('Atmosphere object initialised')

    def get_coupled_planet_mu(self):

        # calculate the absolute mixing ratio of inactive gases
        inactive_mixratio_profile = np.zeros((self.ninactivegases, self.nlayers))
        for i in xrange(self.ninactivegases):
            inactive_mixratio_profile[i, :] = self.inactive_mixratio_profile[i,:]*(1. - np.sum(self.active_mixratio_profile, axis=0))

        # get mu for each layer
        mu = np.zeros(self.nlayers)
        for i in xrange(self.nlayers):
            for idx, gasname in enumerate(self.params.atm_active_gases):
                mu[i] += self.active_mixratio_profile[idx, i] * get_molecular_weight(gasname)
            for idx, gasname in enumerate(self.params.atm_inactive_gases):
                mu[i] += inactive_mixratio_profile[idx, i] * get_molecular_weight(gasname)
            #logging.debug('Mean molecular weight for layer %i is %.4f' % (i, mu[i]/AMU))

        return mu

    # get the atmospheric scale height
    def get_scale_height(self, T=None, g=None, mu=None):


        # here we might use a different approach, similar to Venot
        if not T:
            T = self.temperature_profile
        if not g:
            g = self.planet_grav
        if not mu:
            mu = self.planet_mu

        scaleheight =  (KBOLTZ*T)/(mu*g)
        if len(scaleheight) > 1:
            scaleheight = np.average(scaleheight)

        return scaleheight

    # get the surface gravity of the planet
    def get_surface_gravity(self, mass=None, radius=None):

        if not mass:
            mass = self.planet_mass
        if not radius:
            radius = self.planet_radius
        return (G * mass) / (radius**2)

    # get the altitude profile
    def get_altitude_profile(self, P=None):
        # todo allow for variable scale height...
        if P is None:
            P = self.pressure_profile
        return (-1.)*self.scale_height*np.log(P/self.params.atm_max_pres)

    # get the pressure profile
    def get_pressure_profile(self, Pmax=None, num_scaleheights=None):
        if not Pmax:
            Pmax = self.max_pressure
        if not num_scaleheights:
            num_scaleheights = self.params.atm_num_scaleheights
        Pmin = Pmax * np.exp(-num_scaleheights)
        P = np.linspace(np.log(Pmin), np.log(Pmax), self.nlayers)
        return np.exp(P)[::-1]

    # get the density profile
    def get_density_profile(self, T=None, P=None):
        if P is None:
            P = self.pressure_profile
        if T is None:
            T = self.temperature_profile
        return (P)/(KBOLTZ*T)

    # calculates non-linear sampling grid for TP profile from provided covariance
    def get_TP_sample_grid(self, covmat, delta=0.02):

        Pindex = [0]
        for i in range(self.nlayers-1):
            if np.abs(covmat[0,i] - covmat[0,Pindex[-1]]) >= delta:
                Pindex.append(i)
            elif (i - Pindex[-1]) >= 10:
                Pindex.append(i)
        Pindex.append(self.nlayers-1)

        self.P_index = Pindex
        self.P_sample   = self.pressure_profile[Pindex]

    # get sigma array from data.sigma_dict. Interpolate sigma array to pressure profile
    def get_sigma_array(self):
        pressure_profile_bar = self.pressure_profile/1e5
        sigma_array = np.zeros((self.nactivegases, len(self.pressure_profile), len(self.data.sigma_dict['t']), self.data.int_nwngrid))
        for mol_idx, mol_val in enumerate(self.params.atm_active_gases):
            sigma_in = self.data.sigma_dict['xsecarr'][mol_val]
            for pressure_idx, pressure_val in enumerate(pressure_profile_bar):
                for temperature_idx, temperature_val in enumerate(self.data.sigma_dict['t']):
                    for wno_idx, wno_val in enumerate(self.data.int_wngrid):
                        sigma_array[mol_idx, pressure_idx, temperature_idx, wno_idx] = \
                            np.interp(pressure_val, self.data.sigma_dict['p'], sigma_in[:,temperature_idx,wno_idx])
        return sigma_array

    def get_sigma_rayleigh_array(self):
        sigma_rayleigh_array = np.zeros((self.nactivegases+self.ninactivegases, self.data.int_nwngrid))
        for mol_idx, mol_val in enumerate(self.params.atm_active_gases+self.params.atm_inactive_gases):
            sigma_rayleigh_array[mol_idx,:] =  self.data.sigma_rayleigh_dict[mol_val]
        return sigma_rayleigh_array

    def get_sigma_cia_array(self):
        sigma_cia_array = np.zeros((len(self.params.atm_cia_pairs), len(self.data.sigma_cia_dict['t']), self.data.int_nwngrid))
        for pair_idx, pair_val in enumerate(self.params.atm_cia_pairs):
            sigma_cia_array[pair_idx,:,:] = self.data.sigma_cia_dict['xsecarr'][pair_val]
        return sigma_cia_array

    def get_cia_idx(self):
        # return the gas indexes of the molecules inside the pairs
        # used to get the mixing ratios of the individual molecules in the cpp pathintegral
        # the index refers to the full array of active_gas + inactive_gas
        cia_idx = np.zeros((len(self.params.atm_cia_pairs)*2), dtype=int)
        c = 0
        for pair_idx, pair_val in enumerate(self.params.atm_cia_pairs):
            for mol_idx, mol_val in enumerate(pair_val.split('-')):
                try:
                    cia_idx[c] = self.params.atm_active_gases.index(mol_val)
                except ValueError:
                    cia_idx[c] = self.nactivegases + self.params.atm_inactive_gases.index(mol_val)
                c += 1
        return cia_idx

    def update_atmosphere(self):

        self.planet_grav = self.get_surface_gravity()
        self.pressure_profile = self.get_pressure_profile()
        self.scale_height = self.get_scale_height()
        self.altitude_profile = self.get_altitude_profile()
        self.density_profile = self.get_density_profile()


    #####################
    # Everything below is related to Temperature Pressure Profiles

    def set_TP_profile(self, profile=None):
        '''
        Decorator supplying TP_profile with correct TP profile function.
        Only the free parameters will be provided to the function after TP profile
        is set.
        '''
        if profile is not None: #implicit or explicit TP_type setting
            self.TP_type = profile

        if self.TP_type == 'isothermal':
            _profile = self._TP_isothermal
        elif self.TP_type == 'guillot':
            _profile = self._TP_guillot2010
        elif self.TP_type == 'rodgers':
            _profile = self._TP_rodgers2000
        elif self.TP_type == 'hybrid':
            _profile = self._TP_hybrid
        elif self.TP_type == '2point':
            _profile = self._TP_2point
        elif self.TP_type == '3point':
            _profile = self._TP_3point
        else:
            logging.error('Invalid TP profile name')

        def tpwrap(fit_params, **kwargs):
            return self._TP_profile(_profile, fit_params, **kwargs)

        self.TP_profile = tpwrap  #setting TP_profile
        self.TP_setup = True #flag that allows TP profile internal things to be run once only. Sets to False after execution

    def _TP_profile(self, TP_function, TP_params, **kwargs):
        '''
        TP profile decorator. Takes given TP profile function and fitting parameters
        To generate Temperature, Pressure, Column Density (T, P, X) grids

        fit_params depend on TP_profile selected.
        INDEX splits column densities from TP_profile parameters, INDEX = [Chi, TP]
        '''

        #generating TP profile given input TP_function
        T = TP_function(TP_params, **kwargs)

        self.TP_setup = False #running profile setup only on first call

        return T

    def _TP_isothermal(self, TP_params):
        '''
        TP profile for isothermal atmosphere. Follows the old implementation.
        '''

        T = np.zeros((self.nlayers))
        T[:] = TP_params

        return T

    def _TP_guillot2010(self, TP_params):
        '''
        TP profile from Guillot 2010, A&A, 520, A27 (equation 49)
        Using modified 2stream approx. from Line et al. 2012, ApJ, 729,93 (equation 19)

        Free parameters required:
            - T_irr    = planet equilibrium temperature (Line fixes this but we keep as free parameter)
            - kappa_ir = mean infra-red opacity
            - kappa_v1 = mean optical opacity one
            - kappa_v2 = mean optical opacity two
            - alpha    = ratio between kappa_v1 and kappa_v2 downwards radiation stream

        Fixed parameters:
            - T_int    = internal planetary heat flux (can be largely ignored. line puts it on 200K for hot jupiter)
            - P        = Pressure grid, fixed to self.P
            - g        = surface gravity, fixed to self.planet_grav
        '''

        # assigning fitting parameters
        T_irr = TP_params[0];
        kappa_ir = TP_params[1];
        kappa_v1 = TP_params[2];
        kappa_v2 = TP_params[3];
        alpha = TP_params[4]

        gamma_1 = kappa_v1/(kappa_ir + 1e-10); gamma_2 = kappa_v2/(kappa_ir + 1e-10)
        tau = kappa_ir * self.pressure_profile / self.planet_grav

        T_int = 200 # todo internal heat parameter looks suspicious... needs looking at.

        def eta(gamma, tau):
            part1 = 2.0/3.0 + 2.0 / (3.0*gamma) * (1.0 + (gamma*tau/2.0 - 1.0) * np.exp(-1.0 * gamma * tau))
            part2 = 2.0 * gamma / 3.0 * (1.0 - tau**2/2.0) * spe.expn(2,(gamma*tau))
            return part1 + part2

        T4 = 3.0*T_int**4/4.0 * (2.0/3.0 + tau) + 3.0*T_irr**4/4.0 *(1.0 - alpha) * eta(gamma_1,tau) + 3.0 * T_irr**4/4.0 * alpha * eta(gamma_2,tau)
        T = T4**0.25

        return np.asarray(T)

    def _TP_rodgers2000(self, TP_params, h=None, covmatrix=None):
        '''
        Layer-by-layer temperature - pressure profile retrieval using dampening factor
        Introduced in Rodgers (2000): Inverse Methods for Atmospheric Sounding (equation 3.26)
        Featured in NEMESIS code (Irwin et al., 2008, J. Quant. Spec., 109, 1136 (equation 19)
        Used in all Barstow et al. papers.

        Free parameters required:
            - T  = one temperature per layer of Pressure (P)

        Fixed parameters:
            - P  = Pressure grid, fixed to self.pressure_profile
            - h  = correlation parameter, in scaleheights, Line et al. 2013 sets this to 7, Irwin et al sets this to 1.5
                  may be left as free and Pressure dependent parameter later.
        '''
        if h is None:
            h = self.params.tp_corrlength

        # assigning parameters
        T_init = TP_params

#         covmatrix = np.zeros((self.nlayers,self.nlayers))
#         for i in xrange(self.nlayers):
#                 covmatrix[i,:] = np.exp(-1.0* np.abs(np.log(self.pressure_profile[i]/self.pressure_profile[:]))/h)

        if covmatrix is None: #if covariance not provided, generate
            if self.TP_setup: #run only once and save
                self.rodgers_covmat = np.zeros((self.nlayers,self.nlayers))
                for i in xrange(self.nlayers):
                    self.rodgers_covmat[i,:] = np.exp(-1.0* np.abs(np.log(self.pressure_profile[i]/self.pressure_profile[:]))/h)
        else:
            self.rodgers_covmat = covmatrix

        T = np.zeros((self.nlayers)) #temperature array

        #correlating temperature grid with covariance matrix
        for i in xrange(self.nlayers):
#             covmat  = np.exp(-1.0* np.abs(np.log(self.pressure_profile[i]/self.pressure_profile[:]))/h)
            weights = self.rodgers_covmat[i,:] / np.sum(self.rodgers_covmat[i,:])
            T[i]    = np.sum(weights*T_init)

#         plt.figure(3)
#         plt.imshow(self.rodgers_covmat,origin='lower')
#         plt.colorbar()
#         plt.show()

        #sets list of ascii parameter names. This is used in output module to compile parameters.dat
        if self.TP_setup:
            self.TP_params_ascii = []
            for i in xrange(self.nlayers):
                self.TP_params_ascii.append('T_{0}'.format(str(i)))
        return T

    def _TP_hybrid(self, TP_params, h=None):
        '''
        Layer-by-layer temperature pressure profile. It is a hybrid between the _TP_rodgers2000 profile and
        a second (externally calculated) covariance matrix. The external covariance can be calculated
        using a maximum likelihood retrieval of the TP profile before (or similar).
        The hybrid covariance is given by Cov_hyb = (1-alpha) * Cov_TP_rodgers200 + alpha * Cov_external

        Free parameters required:
            - alpha  = weighting parameter between covariance 1 and 2
            - T      = one temperature per layer of Pressure (P)

        Fixed parameters:
            - P  = Pressure grid, fixed to self.pressure_profile
            - h  = correlation parameter, in scaleheights, Line et al. 2013 sets this to 7, Irwin et al sets this to 1.5
                  may be left as free and Pressure dependent parameter later.
        '''
        if h is None:
            h = self.params.tp_corrlength

        #if self.TP_setup:
        T = np.zeros((self.nlayers)) #temperature array

        #assigning parameters
        alpha  = TP_params[0]

        T_init = TP_params[1:]
        covmatrix = self.hybrid_covmat

        #interpolating fitting temperatures to full grid
        T_interp = np.interp(np.log(self.pressure_profile[::-1]),np.log(self.P_sample[::-1]),T_init[::-1])[::-1]

        if self.TP_setup: #run only once and save
            self.rodgers_covmat = np.zeros((self.nlayers,self.nlayers))
            for i in xrange(self.nlayers):
                self.rodgers_covmat[i,:] = np.exp(-1.0* np.abs(np.log(self.pressure_profile[i]/self.pressure_profile[:]))/h)

        T[:] = 0.0 #temperature array
        cov_hybrid = (1.0-alpha) * self.rodgers_covmat + alpha * covmatrix

        #correlating temperature grid with covariance matrix
        for i in xrange(self.nlayers):
            weights = cov_hybrid[i,:] / np.sum(cov_hybrid[i,:])
            T[i]    = np.sum(weights*T_interp)

#             plt.plot(cov_hybrid[i,:])
#         plt.ion()
#         plt.figure(2)
#         plt.clf()
# #         plt.plot(self.T,self.pressure_profile,'blue')
# #         plt.plot(T_interp,self.pressure_profile,'k')
#         plt.plot(T_init,self.P_sample,'ro')
#         plt.yscale('log')
# #         xlabel('Temperature')
# #         ylabel('Pressure (Pa)')
#         plt.gca().invert_yaxis()
#         plt.draw()
#
#         plt.ion()
#         plt.figure(3)
#         plt.clf()
#         plt.plot(self.T,self.pressure_profile,'blue')
# #         plt.plot(T_interp,self.pressure_profile,'k')
# #         plt.plot(T_init,self.P_sample,'ro')
#         plt.yscale('log')
# #         xlabel('Temperature')
# #         ylabel('Pressure (Pa)')
#         plt.gca().invert_yaxis()
#         plt.draw()


#         plt.figure(3)
#         plt.plot(weights)
#         plt.show()
#         exit()

        return T

    def set_TP_hybrid_covmat(self,covariance):
        '''
        Setting external covariance for _TP_hybrid
        '''
        self.hybrid_covmat = covariance


    def _TP_2point(self,TP_params):
        '''
        Two point TP profile. Simplest possible profile only fitting for the surface temperature and tropopause temp.
        and pressure. Atmosphere above tropopause is isothermal. Temperature is linearly interpolated in log space.
        No inversion possible here.

        Free parameters required:
            - T1 = surface temperature (at 10bar)
            - T2 = temperature at tropopause (given as difference from T1)
            - P1 = pressure at tropopause

        Fixed parameters:
            - Pressure grid (self.pressure_profile)
        '''

        maxP = np.max(self.pressure_profile)
        minP = np.min(self.pressure_profile)

        T_trop = TP_params[0] - TP_params[1]

        P_params = [maxP,TP_params[-1],minP]
        T_params = [TP_params[0],T_trop,T_trop]

        #creating linear T-P profile
        T = np.interp(np.log(self.pressure_profile[::-1]), np.log(P_params[::-1]), T_params[::-1])

        return T[::-1]


    def _TP_3point(self,TP_params):
        '''
        Same as 2point TP profile but adds one extra point between surface and troposphere

        Free parameters required:
            - T1 = surface temperature (at 10bar)
            - T2 = point 1 temperature (given as difference from T1)
            - P1 = point 1 pressure
            - T3 = point 2 temperature (given as difference from T1)
            - P2 = point 2 pressure

        Fixed parameters
            - Pressure grid (self.pressure_profile)
        '''

        maxP = np.max(self.pressure_profile)
        minP = np.min(self.pressure_profile)

        T_point1 = TP_params[0] - TP_params[1]
        T_point2 = T_point1 - TP_params[2]
        P_params = [maxP,TP_params[-2],TP_params[-1],minP]
        T_params = [TP_params[0],T_point1,T_point2, T_point2]

        #creating linear T-P profile
        T = np.interp(np.log(self.pressure_profile[::-1]), np.log(P_params[::-1]), T_params[::-1])

        return T[::-1]

