# Copyright 2016 Allen Institute for Brain Science
# This file is part of Allen SDK.
#
# Allen SDK is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# Allen SDK is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Allen SDK.  If not, see <http://www.gnu.org/licenses/>.

from o_p_analysis import OPAnalysis
import scipy.stats as st
import pandas as pd
import numpy as np
from math import sqrt
import logging

class DriftingGrating(OPAnalysis):
    _log = logging.getLogger('allensdk.brain_observatory.drifting_grating')    

    def __init__(self, brain_observatory_analysis, **kwargs):
        super(DriftingGrating, self).__init__(brain_observatory_analysis, **kwargs)                   
        stimulus_table = self.brain_observatory_analysis.nwb.get_drifting_gratings_stimulus_table()
        self.stim_table = stimulus_table.fillna(value=0.)     
        self.sweeplength = 60#self.sync_table['end'][1] - self.sync_table['start'][1]
        self.interlength = 30#self.sync_table['start'][2] - self.sync_table['end'][1]
        self.extralength = 0
        self.orivals = np.unique(self.stim_table.orientation).astype(int)
        self.tfvals = np.unique(self.stim_table.temporal_frequency).astype(int)
        self.number_ori = len(self.orivals)
        self.number_tf = len(self.tfvals)            
        self.sweep_response, self.mean_sweep_response, self.pval = self.get_sweep_response()
        self.response = self.get_response()
        self.peak = self.get_peak()
    
    def get_response(self):
        DriftingGrating._log.info("Calculating mean responses")
        
        response = np.empty((self.number_ori, self.number_tf, self.numbercells+1, 3))
        def ptest(x):
            return len(np.where(x<(0.05/(8*5)))[0])
            
        for ori in self.orivals:
            ori_pt = np.where(self.orivals == ori)[0][0]
            for tf in self.tfvals:
                tf_pt = np.where(self.tfvals == tf)[0][0]
                subset_response = self.mean_sweep_response[(self.stim_table.temporal_frequency==tf)&(self.stim_table.orientation==ori)]
                subset_pval = self.pval[(self.stim_table.temporal_frequency==tf)&(self.stim_table.orientation==ori)]
                response[ori_pt, tf_pt, :, 0] = subset_response.mean(axis=0)
                response[ori_pt, tf_pt, :, 1] = subset_response.std(axis=0)/sqrt(len(subset_response))
                response[ori_pt, tf_pt, :, 2] = subset_pval.apply(ptest, axis=0)
        return response
    
    def get_peak(self):
        '''finds the peak response for each cell'''
        DriftingGrating._log.info('Calculating peak response properties')
        
        peak = pd.DataFrame(index=range(self.numbercells), columns=('ori_dg','tf_dg','response_variability_dg','osi_dg','dsi_dg','peak_dff_dg','ptest_dg', 'p_run_dg','run_modulation_dg','cv_dg'))

        orivals_rad = np.deg2rad(self.orivals)
        for nc in range(self.numbercells):
            cell_peak = np.where(self.response[:,1:,nc,0] == np.nanmax(self.response[:,1:,nc,0]))
            prefori = cell_peak[0][0]
            preftf = cell_peak[1][0]+1
            peak.ori_dg.iloc[nc] = prefori
            peak.tf_dg.iloc[nc] = preftf
            peak.response_variability_dg.iloc[nc] = self.response[prefori, preftf, nc, 2]/0.15
            pref = self.response[prefori, preftf, nc, 0]            
            orth1 = self.response[np.mod(prefori+2, 8), preftf, nc, 0]
            orth2 = self.response[np.mod(prefori-2, 8), preftf, nc, 0]
            orth = (orth1+orth2)/2
            null = self.response[np.mod(prefori+4, 8), preftf, nc, 0]
            
            tuning = self.response[:, preftf, nc, 0]                
            CV_top = np.empty((8))
            for i in range(8):
                CV_top[i] = (tuning[i]*np.exp(1j*2*orivals_rad[i])).real
            peak.cv_dg.iloc[nc] = np.abs(CV_top.sum()/tuning.sum())
            
            peak.osi_dg.iloc[nc] = (pref-orth)/(pref+orth) 
            peak.dsi_dg.iloc[nc] = (pref-null)/(pref+null)
            peak.peak_dff_dg.iloc[nc] = pref
            
            groups = []
            for ori in self.orivals:
                for tf in self.tfvals[1:]:
                    groups.append(self.mean_sweep_response[(self.stim_table.temporal_frequency==tf)&(self.stim_table.orientation==ori)][str(nc)])
            groups.append(self.mean_sweep_response[self.stim_table.temporal_frequency==0][str(nc)])
            f,p = st.f_oneway(*groups)
            peak.ptest_dg.iloc[nc] = p
            
            subset = self.mean_sweep_response[(self.stim_table.temporal_frequency==self.tfvals[preftf])&(self.stim_table.orientation==self.orivals[prefori])]
            subset_stat = subset[subset.dx<1]
            subset_run = subset[subset.dx>=1]
            if (len(subset_run)>2) & ( len(subset_stat)>2):
                (f, peak.p_run_dg.iloc[nc]) = st.ks_2samp(subset_run[str(nc)], subset_stat[str(nc)])
                peak.run_modulation_dg.iloc[nc] = subset_run[str(nc)].mean()/subset_stat[str(nc)].mean()
            else:
                peak.p_run_dg.iloc[nc] = np.NaN
                peak.run_modulation_dg.iloc[nc] = np.NaN
        return peak
    
