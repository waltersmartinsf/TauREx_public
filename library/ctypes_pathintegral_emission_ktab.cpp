/* 

    TauREx v2 - Development version - DO NOT DISTRIBUTE

    Forward model for emission

    Developers: Ingo Waldmann, Marco Rocchetto (University College London)


    For both openmp and single core versions compile with g++:

             g++ -fPIC -shared -o ctypes_pathintegral_emission_ktab.so ctypes_pathintegral_emission_ktab.cpp

    or Intel compiler:

             icc -fPIC -shared -o ctypes_pathintegral_emission_ktab.so ctypes_pathintegral_emission_ktab.cpp


 */

#include <stdio.h>
#include <iostream>
#include <cmath>
#include <algorithm>
#include <vector>
#include <stdlib.h>
#include <iostream>
#include <string>
#include <sstream>

using namespace std;

extern "C" {

    void path_integral(const double * wngrid,
                       const int nwngrid,
                       const int nlayers,
                       const int nactive,
                       const int ninactive,
                       const int rayleigh,
                       const int cia,

//                       const double * sigma_array,
//                       const double * sigma_temp,
//                       const int sigma_ntemp,

                       const double * ktab_array,
                       const double * ktab_temp,
                       const int ktab_ntemp,
                       const int ngauss,
                       const double * ktab_weights,


                       const double * sigma_rayleigh,
                       const int cia_npairs,
                       const double * cia_idx,
                       const int cia_nidx,
                       const double * sigma_cia,
                       const double * sigma_cia_temp,
                       const int sigma_cia_ntemp,
                       const double * density,
                       const double * z,
                       const double * active_mixratio,
                       const double * inactive_mixratio,
                       const double * temperature,
                       const double planet_radius,
                       const double star_radius,
                       const double * star_sed,
                       void * FpFsv,
                       void * tauv) {

        double * FpFs = (double *) FpFsv;
        double * contrib = (double *) tauv;

        // setting up arrays and variables
        double* dz = new double[nlayers];
        double* ktab_interp = new double[ngauss*nwngrid*nlayers*nactive];
        double* sigma_cia_interp = new double[nwngrid * nlayers * cia_npairs];
        double sigma, sigma_l, sigma_r;
        double tau, tau_cia, dtau, dtau1, tau_sum1, tau_sum2, dtau_cia, mu, tau_tot,eta;
        double p;
        double mu1, mu2, mu3, mu4, w1, w2, w3, w4;
        int count, count2, t_idx;
        double F_total, BB_wl, exponent;
        double I1, I2, I3, I4;
        double h, c, kb, pi;
        double x1_idx[cia_npairs][nlayers];
        double x2_idx[cia_npairs][nlayers];

        int l;

        h = 6.62606957e-34;
        c = 299792458;
        kb = 1.3806488e-23;
        pi= 3.14159265359;

        // set the four zenith angles sampled at four gaussian quadrature points
        mu1 = 0.1834346;
        mu2 = 0.5255324;
        mu3 = 0.7966665;
        mu4 = 0.9602899;
        // gaussian quadrature weights
        w1 = 0.3626838;
        w2 = 0.3137066;
        w3 = 0.2223810;
        w4 = 0.1012885;

        //dz array
        for (int j=0; j<(nlayers); j++) {
            if ((j+1) == nlayers) {
                dz[j] = z[j] - z[j-1];
            } else {
                dz[j] = z[j+1] - z[j];
            }
        }

        // interpolate ktab array to the temperature profile
        for (int j=0; j<nlayers; j++) {
            cout << temperature[j] << endl;
            if (temperature[j] > ktab_temp[ktab_ntemp-1]) { // temperature higher than ktab
                for (int wn=0; wn<nwngrid; wn++) {
                    for (int l=0;l<nactive;l++) {
                        for (int g=0; g<ngauss; g++) {
                            ktab_interp[g + ngauss*(wn + nwngrid*(j + l*nlayers))] =  ktab_array[g + ngauss*(wn + nwngrid*(ktab_ntemp-1 + ktab_ntemp*(j + l*nlayers)))];
                        }
                    }
                }
            } else if (temperature[j] < ktab_temp[0]) { // temperature lower than ktab
                for (int wn=0; wn<nwngrid; wn++) {
                    for (int l=0;l<nactive;l++) {
                        for (int g=0; g<ngauss; g++) {
                            ktab_interp[g + ngauss*(wn + nwngrid*(j + l*nlayers))] = ktab_array[g + ngauss*(wn + nwngrid*(ktab_ntemp*(j + l*nlayers)))];
                        }
                    }
                }
            } else {
                if (ktab_ntemp == 1) { // This only happens for create_spectrum (when temperature is part of sigma_t)
                    for (int wn=0; wn<nwngrid; wn++) {
                        for (int l=0;l<nactive;l++) {
                            for (int g=0; g<ngauss; g++) {
                                ktab_interp[g + ngauss * (wn + nwngrid*(j + l*nlayers))] = ktab_array[g + ngauss*(wn + nwngrid*(ktab_ntemp*(j + l*nlayers)))];
                            }
                        }
                    }
                } else {
                    for (int t=1; t<ktab_ntemp; t++) {
                        if ((temperature[j] >= ktab_temp[t-1]) && (temperature[j] < ktab_temp[t])) {
                            #pragma omp parallel for private(sigma_l, sigma_r, sigma)
                            for (int wn=0; wn<nwngrid; wn++) {
                                for (int l=0;l<nactive;l++) {
                                    for (int g=0; g<ngauss; g++) {
                                        sigma_l = ktab_array[g + ngauss*(wn + nwngrid*(t-1 + ktab_ntemp*(j + l*nlayers)))];
                                        sigma_r = ktab_array[g + ngauss*(wn + nwngrid*(t + ktab_ntemp*(j + l*nlayers)))];
                                        sigma = sigma_l + (sigma_r-sigma_l)*(log10(temperature[j])-log10(ktab_temp[t-1]))/(log10(ktab_temp[t])-log10(ktab_temp[t-1]));
                                        ktab_interp[g + ngauss*(wn + nwngrid*(j + l*nlayers))] = sigma;
                                     }
                                }
                            }
                        }
                    }
                }
            }
        }

        // interpolate sigma CIA array to the temperature profile
        for (int j=0; j<nlayers; j++) {
            if (sigma_cia_ntemp == 1) { //
                for (int wn=0; wn<nwngrid; wn++) {
                     for (int l=0;l<cia_npairs;l++) {
                        sigma_cia_interp[wn +  nwngrid*(j + l*nlayers)] = sigma_cia[wn + nwngrid*(sigma_cia_ntemp*l)];
                     }
                }
            } else {
                if (temperature[j] > sigma_cia_temp[sigma_cia_ntemp-1]) {
                    for (int wn=0; wn<nwngrid; wn++) {
                         for (int l=0;l<cia_npairs;l++) {
                            sigma_cia_interp[wn +  nwngrid*(j + l*nlayers)] = sigma_cia[wn + nwngrid*(sigma_cia_ntemp-1 + sigma_cia_ntemp*l)];
                         }
                    }
                } else if  (temperature[j] <  sigma_cia_temp[0]) {
                    for (int wn=0; wn<nwngrid; wn++) {
                         for (int l=0;l<cia_npairs;l++) {
                            sigma_cia_interp[wn +  nwngrid*(j + l*nlayers)] = sigma_cia[wn + nwngrid*(sigma_cia_ntemp*l)];
                         }
                    }
                } else {
                    for (int t=1; t<sigma_cia_ntemp; t++) {
                        if ((temperature[j] > sigma_cia_temp[t-1]) && (temperature[j] < sigma_cia_temp[t])) {
                            #pragma omp parallel for private(sigma_l, sigma_r, sigma)
                            for (int wn=0; wn<nwngrid; wn++) {
                                for (int l=0;l<cia_npairs;l++) {
                                    sigma_l = sigma_cia[wn + nwngrid*(t-1 + sigma_cia_ntemp*l)];
                                    sigma_r = sigma_cia[wn + nwngrid*(t + sigma_cia_ntemp*l)];
                                    sigma = sigma_l + (sigma_r-sigma_l)*(temperature[j]-sigma_cia_temp[t-1])/(sigma_cia_temp[t]-sigma_cia_temp[t-1]);
                                    sigma_cia_interp[wn +  nwngrid*(j + l*nlayers)] = sigma;
                                }
                            }
                        }
                    }
                 }
            }
        }


        // get mixing ratio of individual molecules in the collision induced absorption (CIA) pairs
        for (int c=0; c<cia_npairs;c++) {
             if (int(cia_idx[c*2]) >= nactive) {
                for (int j=0;j<nlayers;j++) {

                    x1_idx[c][j] = inactive_mixratio[j+nlayers*(int(cia_idx[c*2])-nactive)];
                    x2_idx[c][j] = inactive_mixratio[j+nlayers*(int(cia_idx[c*2+1])-nactive)];
                }
             } else {
                for (int j=0;j<nlayers;j++) {
                    x1_idx[c][j] = active_mixratio[j+nlayers*int(cia_idx[c*2])];
                    x2_idx[c][j] = active_mixratio[j+nlayers*int(cia_idx[c*2+1])];
                }
            }
         }


        // calculate emission

        #pragma omp parallel for private(F_total, I1, I2, I3, I4, dtau, tau_sum1, tau_sum2, eta, exponent, BB_wl)
        for (int wn=0; wn < nwngrid; wn++) {

            F_total = 0.0;

            for (int g=0; g<ngauss; g++) {


                 // Contribution from the surface.


//                tau_sum1 = 0.;
//                tau_sum2 = 0.;
//                eta = 1.0;
//
//                // calculate BB for temperature of layer 0
//                exponent = exp((h * c) / ((10000./wngrid[wn])*1e-6  * kb * temperature[0]));
//                BB_wl = ((2.0*h*pow(c,2))/pow((10000./wngrid[wn])*1e-6,5) * (1.0/(exponent - 1)))* 1e-6; // (W/m^2/micron)
//
//
//                // assume only one gas, and no cia or rayleigh
//                l = 0;
//                tau_sum1 += ktab_interp[g + ngauss*(wn + nwngrid*((0) + l*nlayers))]* density[0] * dz[0];
//
//                for (int k=0; k<(nlayers); k++) {
//
//                    // assume only one gas, and no cia or rayleigh
//                    l = 0;
//                    tau_sum1 += ktab_interp[g + ngauss*(wn + nwngrid*((k) + l*nlayers))]* density[k] * dz[k];
//                 }
//
//                // calculate individual intensities at zenith angles sampled at 4 gaussian quadrature points
//                I1 += BB_wl * ( exp(-tau_sum2/mu1))* eta;
//                I2 += BB_wl * ( exp(-tau_sum2/mu2))* eta;
//                I3 += BB_wl * ( exp(-tau_sum2/mu3))* eta;
//                I4 += BB_wl * ( exp(-tau_sum2/mu4))* eta;

                I1 = 0;
                I2 = 0;
                I3 = 0;
                I4 = 0;

                // loop through layers from bottom to TOA
                for (int j=0; j<(nlayers-1); j++) {

                    // calculate BB for temperature of layer j
                    exponent = exp((h * c) / ((10000./wngrid[wn])*1e-6  * kb * temperature[j]));
                    BB_wl = ((2.0*h*pow(c,2))/pow((10000./wngrid[wn])*1e-6,5) * (1.0/(exponent - 1)))* 1e-6; // (W/m^2/micron)

                    // calculate tau from j+1 to TOA
                    tau_sum1 = 0.;
                    for (int k=j+1; k < nlayers; k++) { // loop through layers to add dtau[k]

                       // again assume no cia and rayleigh, and only one gas
                        l = 0;
                        tau_sum1 += ktab_interp[g + ngauss*(wn + nwngrid*((k) + l*nlayers))]* density[k] * dz[k];
                    }

                    // calculate tau from j to TOA  (just add dtau[j] to tau_sum1 calculated above)
                    dtau = 0;
                    dtau +=  (ktab_interp[g + ngauss*(wn + nwngrid*((j) + l*nlayers))] * density[j] * dz[j]);
                    tau_sum2 = tau_sum1 + dtau;

                    // contribution function
                    contrib[wn + j*nwngrid] = (exp(-tau_sum1) - exp(-tau_sum2));

                    // calculate individual intensities at zenith angles sampled at 4 gaussian quadrature points

                      I1 += BB_wl * ( exp(-tau_sum1/0.66) - exp(-tau_sum2/0.66));

//                    I1 += BB_wl * ( exp(-tau_sum1/mu1) - exp(-tau_sum2/mu1));
//                    I2 += BB_wl * ( exp(-tau_sum1/mu2) - exp(-tau_sum2/mu2));
//                    I3 += BB_wl * ( exp(-tau_sum1/mu3) - exp(-tau_sum2/mu3));
//                    I4 += BB_wl * ( exp(-tau_sum1/mu4) - exp(-tau_sum2/mu4));

                }
                I1 = I1 * ktab_weights[g];
//              I2 = I2 * ktab_weights[g];
//              I3 = I3 * ktab_weights[g];
//              I4 = I4 * ktab_weights[g];

                // Integrating over zenith angle by suming the 4 intensities multiplied by the zenith angle and the
                // four quadrature weights. Get flux by multiplying by 2 pi
                //F_total +=  2.0*pi*(I1*mu1*w1 + I2*mu2*w2 + I3*mu3*w3 + I4*mu4*w4);

                F_total += 2.* pi * I1 * 0.66;

            }

            FpFs[wn] = (F_total/star_sed[wn]) * pow((planet_radius/star_radius), 2);

        }

        delete[] dz;
        delete[] ktab_interp;
        delete[] sigma_cia_interp;
        dz = NULL;
        ktab_interp = NULL;
        sigma_cia_interp = NULL;

    }
}
