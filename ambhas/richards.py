# -*- coding: utf-8 -*-
"""
Created on Mon Mar 12 17:41:54 2012

@author: sat kumar tomer
@email: satkumartomer@gmail.com
@website: www.ambhas.com
"""

from __future__ import division
import numpy as np
import xlrd
from Scientific.IO import NetCDF as nc
import datetime
import matplotlib.pyplot as plt
from BIP.Bayes.lhs import lhs
from scipy import stats
np.seterr(all='raise')

class RICHARDS_1D():
    """
    This is the main class of the RICHARDS_1D.
    This simulates the flow in unsaturated porus media
    
    This will read the input data,
    do the processing
    and then write the output files
    
    """
    
    def __init__(self,input_file):
        """
        Input:
            input_file: the file which contains all the information
            including forcing and parameters.
        """      
        self.input_file = input_file
        
        # read the input data
        self._read_input()
        
        # initialize the variables and output file
        self.initialize()
        
        ################ run the model ########################
        for t in range(self.max_t):
            self.t = t
              
            # get forcing data at current time step        
            self._get_forcing()
            
            # call the unsat module
            self._unsat()
                
        self.nc_file.close() # close the output file
         
     
            
    def _read_input(self):
        """
        This checks if all the required input sheets are present in the xls file,
        read the data from input file, which can be used later in other functions
        """
    
        # list of required files in the input directory
        input_sheets = ['ind', 'forcing', 'initial_condition', 'units', 'temporal_info',
                       'spatial_info', 'soil_hyd_par', 'output_par']
        
        # check if all the required sheets are present or not
        self._check_sheets(input_sheets, self.input_file)
        
        # read the legend
        self._read_ind()
        
        # read the spatial data
        self._read_spatial()
        
        # read the temporal data
        self._read_temporal()

        # read the units 
        self._read_units()
        
        # read the initial condition
        self._read_initial_condition()
        
        # read the soil hydraulic properties data
        self._read_shp()
        
        # read the forcing infomation
        self._read_forcing()
        
        # read the outfile name
        self._read_ofile_name()
        
        # print the reading status
        output_message = 'Input data reading completed sucessfully'
        self._colored_output(output_message, 32)
    
    def _check_sheets(self, check_sheets, check_file):
        """
        This functions check if all the sheets needed to model are present  
        in check_file
        
        """
        # open the xls file and get its sheets
        foo = xlrd.open_workbook(check_file)
        check_sheet_names = foo.sheet_names()
        
        for check_sheet in check_sheets:
            if check_sheet not in check_sheet_names:
                output_message = 'The sheet ' + check_sheet + ' is missing'
                self._colored_output(output_message,31)
            

    def _read_ind(self):
        """
        Read the ind sheet
        legend stores the information about the indices of other properties,
        which would be used by all other properties reading functions
        """
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_name('ind')
        # dont read the first line of the xls file
        ind = {}
        for i in range(sheet.nrows-1):
            ind[str(sheet.cell_value(i+1,0))] = int(sheet.cell_value(i+1,1))
                
        self.ind = ind

    def _read_spatial(self):
        """
        Read the spatial info
        """
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_name('spatial_info')
        # get the row number from the ind
        j = self.ind['spatial_info']
        no_layer = int(sheet.cell_value(j,1))
        dz = sheet.cell_value(j,2)
                
        self.no_layer = no_layer
        self.dz = dz
    
    def _read_temporal(self):
        """
        Read the temporal info
        """
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_name('temporal_info')
        #get the row number from the ind
        j = self.ind['temporal_info']
        dt = sheet.cell_value(j,1)
        final_time = sheet.cell_value(j,2)
        
        self.dt_flux = dt
        self.final_time = final_time
    
    
    def _read_units(self):
        """
        read the units of the forcing data
        """
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_name('units')
        #get the row number from the ind
        j = self.ind['units']
        forcing_units = {}
        for i in range(sheet.ncols-1):
            forcing_units[str(sheet.cell_value(0,i+1))] = str(sheet.cell_value(j,i+1))
        self.forcing_units = forcing_units
    
    def _read_initial_condition(self):
        """
        read initial condition
        """
        #get the row number from the ind
        j = self.ind['initial_condition']
        
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_name('initial_condition')
        theta_0 = sheet.cell_value(j,1)
        self.theta = np.tile(theta_0,self.no_layer)
        
    def _read_shp(self):
        """
        read the soil hydraulic parameters
        """
        #get the row number from the ind
        j = self.ind['soil_hyd_par']
        
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_name('soil_hyd_par')
        soil_par = {}
        soil_par['thetar'] = sheet.cell_value(j,1)
        soil_par['thetas'] = sheet.cell_value(j,2)
        soil_par['alpha'] = sheet.cell_value(j,3)
        soil_par['n'] = sheet.cell_value(j,4)
        soil_par['Ks'] = sheet.cell_value(j,5)
        soil_par['l'] = sheet.cell_value(j,6)
        soil_par['evap_0'] = sheet.cell_value(j,7)
        soil_par['evap_1'] = sheet.cell_value(j,8)
        soil_par['m'] = 1-1/soil_par['n']
        self.soil_par = soil_par
    
    
    def _read_forcing(self):
        """
        read the forcing data from xls file
        """
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_name('forcing')
        
        data_len = sheet.nrows-1
        year = np.zeros(data_len)
        doy = np.zeros(data_len)
        rain = np.zeros(data_len)
        pet = np.zeros(data_len)
            
        for i in xrange(data_len):
            year[i] = sheet.cell_value(i+1,0)
            doy[i] = sheet.cell_value(i+1,1)
            rain[i] = sheet.cell_value(i+1,2)
            pet[i] = sheet.cell_value(i+1,3)
                    
        
        self.year = year
        self.doy = doy
        
        # if forcing data was in mm units, covert into m
        if self.forcing_units['rain'] == 'mm':
            self.rain = rain/1000.0
        elif self.forcing_units['rain'] == 'm':
            self.rain = rain
        else:
            raise ValueError("The units of rain should be either 'mm' or 'm' ")

        if self.forcing_units['pet'] == 'mm':
            self.pet = pet/1000.0
        elif self.forcing_units['pet'] == 'm':
            self.pet = pet
        else:
            raise ValueError("The units of PET should be either 'mm' or 'm' ")
            
      

    def _read_ofile_name(self):
        """
        read the forcing data from xls file
        """
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_name('output_par')
        j = self.ind['output_par']
        self.ofile_name = str(sheet.cell_value(j,1))


    def _colored_output(self, output_message, color):
        """
        This functions print  the output_message in the color
        Input:
            output_messgae: the text you want to print
            color: the color in which you want to print text, it could be one of:
                30: Gray
                31: Red
                32: Green
                33: Yellow
                34: Blue
                35: Magneta
                66: Cyan
                37: White
                38: Crimson
                41: Highlighted Red
                42: Highlighted Green 
                43: Highlighted Brown 
                44: Highlighted Blue 
                45: Highlighted Magenta 
                46: Highlighted Cyan
                47: Highlighted Gray 
                48: Highlighted Crimson 
        Output:
            This returns None, but print the output in python shell
        """
                
        print(("\033[31m" +output_message+ "\033[0m").replace('31',str(color)))

    def _get_forcing(self):
        """
        this will give the forcing at time t
        forcing are given in terms of L/T
        """
        self.rain_cur = self.rain[self.t]/self.dt_flux
        self.pet_cur = self.pet[self.t]/self.dt_flux
                
        self.cur_year = self.year[self.t]
        self.cur_doy = self.doy[self.t]
        
    
    def smcf(self, theta, thetar, thetas, alpha, m, n):
        """
        smcf: calculate the smc
        """
        Se = (theta-thetar)/(thetas-thetar)
        Se[Se<0] = 0.01
        Se[Se>1] = 1.0
        smc = alpha*(thetas-thetar)*m*n*pow(Se,1/m+1)*pow(pow(Se,-1/m)-1,m)
        return smc
    
    def theta2psi(self,theta, thetar, thetas, m, n, alpha):
        """
        theta2psi: given the theta calculate the psi
        """
        Se = (theta-thetar)/(thetas-thetar)
        Se[Se<0] = 0.01
        Se[Se>1] = 1.0
        psi = -(1/alpha)*pow(pow(Se,-1/m)-1,1/n)
        psi[psi<-1e6] = -1e6
        return psi
        
    def psi2theta(self,psi, thetar, thetas, alpha, m, n):
         """
         psi2theta: given the theta calculate the pressure head
         """
         if (psi>0):
             theta = thetas
         elif psi<-1e6:
             theta = 1.01*thetar
         else:
             theta = thetar+(thetas-thetar)*pow(1+pow(abs(alpha*psi),n),-m)
         return theta
         
    def theta2kr(self,theta, thetar, thetas, m, l, Ks):
        """
        theta2kr: given the theta, calculate the kr 
        """
        Se = (theta-thetar)/(thetas-thetar)
        Se[Se<0] = 0.01
        Se[Se>1] = 1.0
        kr = Ks*(pow(Se,l))*pow(1-pow(1-pow(Se,1/m),m),2)
        kr[Se<0] = 0
        kr[Se>1] = Ks
        
        return kr
    
    def initialize(self):
        """
        this initializes all the required variables
        and open the netcdf file for writting
        """
        max_t = int(self.final_time/self.dt_flux)
        #max_t = 56
        self.max_t = max_t
        self.iter_dt = 1
                        
        # open file for writing
        file = nc.NetCDFFile(self.ofile_name, 'w')
        setattr(file, 'title', 'output of the model ambhas.richards')
        now = datetime.datetime.now()
        setattr(file, 'description', 'The model was run at %s'%(now.ctime()))
        file.createDimension('depth', self.no_layer)
        file.createDimension('time', self.max_t+1)
        
        # depth
        varDims = 'depth',
        depth = file.createVariable('depth', 'd', varDims)
        depth.units = 'm'
        depth[:] = np.tile(self.dz,self.no_layer).cumsum()-self.dz/2
        
        # time (year and doy)
        varDims = 'time',
        self.nc_year = file.createVariable('year', 'd', varDims)
        self.nc_doy = file.createVariable('doy', 'd', varDims)
        
        # soil moisture
        varDims = 'depth','time'
        self.nc_sm = file.createVariable('sm','d', varDims)
        self.nc_sm.units = 'v/v'
        self.nc_sm[:,0] = self.theta
        
        # recharge and aet
        varDims = 'time',
        self.nc_aet = file.createVariable('aet','d',varDims)
        self.nc_aet.units = 'mm'
        self.nc_recharge = file.createVariable('recharge','d',varDims)
        self.nc_recharge.units = 'mm'
        
        # soil_par
        setattr(file, 'thetar', self.soil_par['thetar'])
        setattr(file, 'thetas', self.soil_par['thetas'])
        setattr(file, 'alpha', self.soil_par['alpha'])
        setattr(file, 'n', self.soil_par['n'])
        setattr(file, 'Ks', self.soil_par['Ks'])
        setattr(file, 'l', self.soil_par['l'])        
        
        self.nc_file = file
                
        
    def _unsat(self):
        """
        top boundary: atmoshpheric
        bottom boundary: gravity drainage
        """
               
        thetar = self.soil_par['thetar']
        thetas = self.soil_par['thetas']
        alpha = self.soil_par['alpha']
        n = self.soil_par['n']
        m = self.soil_par['m']
        l = self.soil_par['l']
        Ks = self.soil_par['Ks']
        nz = self.no_layer
                
        theta = 1.0*self.theta
        
        #delta_theta = (np.abs(flux)).max()
        
        iter_dt = max(24,int(np.ceil(self.rain_cur*self.dt_flux*1000/0.15)))
        self.iter_dt = int(max(iter_dt,0.75*self.iter_dt))
        
        #if self.t == 56:
        #    self.iter_dt = int(self.iter_dt*6)
        #print self.iter_dt
        
        recharge_day = 0
        aet_day = 0
        
        # check for time step
        for i in range(self.iter_dt):
            dt = self.dt_flux/self.iter_dt
            #print dt
            # top boundary value
            smi = (self.theta[0]-self.soil_par['evap_0'])/(self.soil_par['evap_1']-self.soil_par['evap_0'])
            if smi<0: smi=0
            if smi>1: smi=1
            aet = smi*self.pet_cur
            Bvalue = self.rain_cur-aet
        
            K = self.theta2kr(theta,thetar,thetas,m,l,Ks)
            smc = self.smcf(theta,thetar,thetas,alpha,m,n)
            psi = self.theta2psi(theta,thetar,thetas,m,n,alpha)
                        
            #flux boundary condition at the top
            Kmid = np.empty(nz+1)        
            Kmid[0] = 0
            for i in range(1,nz):
                Kmid[i] = 0.5*(K[i]+K[i-1])
            Kmid[nz] = K[nz-1]
            
            #Setting the coefficient for the internal nodes
            A = np.empty(nz)
            B = np.empty(nz)
            C = np.empty(nz)
            D = np.empty(nz)
            dz = self.dz
            dz2 = dz**2
            
            for i in range(nz):
                A[i] = -(Kmid[i]/dz2)
                B[i] = smc[i]/dt+(Kmid[i+1]+Kmid[i])/dz2
                C[i] = A[i]
                D[i] = smc[i]*psi[i]/dt-(Kmid[i+1]-Kmid[i])/dz
            # setting the coefficient for the top bc (flux boundary)
            i = 0        
            A[0] = 0
            B[0] = smc[i]/dt+(Kmid[1])/dz2
            D[0] = smc[i]*psi[i]/dt+(Bvalue-Kmid[1])/dz
            
            # setting the coefficient for the bottom bc: gravity drainage
            B[nz-1] = smc[nz-1]/dt+(Kmid[nz])/dz2
            C[nz-1] = 0
            D[nz-1] = smc[nz-1]*psi[nz-1]/dt-(Kmid[nz]-Kmid[nz-1])/dz
            
            # Solving using the thomas algorithm
            beta = np.empty(nz)
            gamma = np.empty(nz)
            u = np.empty(nz)
            beta[0] = B[0]
            gamma[0] = D[0]/beta[0]
            for i in range(1,nz):
                beta[i] = B[i]-(A[i]*C[i-1])/(beta[i-1])
                gamma[i] = (D[i]-A[i]*gamma[i-1])/(beta[i])
            
            u[nz-1] = gamma[nz-1]
            for i in range(nz-2,-1,-1):
                u[i] = gamma[i]-(C[i]*u[i+1])/beta[i]
            
            # flux computation between nodes
            J = np.empty(nz+1)
            for i in range(1,nz):
                J[i] = Kmid[i]*(1-(u[i]-u[i-1])/dz)
            J[0] = Bvalue
            J[nz] = Kmid[nz]
            
            J[nz] = J[nz]
            # flux updating
            flux = np.diff(J)*dt/dz
            theta = theta - flux
            
            if theta[0]>thetas:
                theta[theta>thetas] = 0.99*thetas
                        
            aet_day += aet*dt 
            recharge_day += J[nz]*dt
                            
        self.theta = theta        
                      
        # write the output
        self.nc_year[self.t] = (self.cur_year)
        self.nc_doy[self.t] = (self.cur_doy)
        self.nc_sm[:,self.t+1] = theta
        self.nc_recharge[self.t] = recharge_day
        self.nc_aet[self.t] = aet_day
        
        # print progress
        if self.t == int(0.25*self.max_t):
            output_message = '25 % completed'
            self._colored_output(output_message, 32)
        
        elif self.t == int(0.5*self.max_t):
            output_message = '50 % completed'
            self._colored_output(output_message, 32)
        
        elif self.t == int(0.75*self.max_t):
            output_message = '75 % completed'
            self._colored_output(output_message, 32)
        
        elif self.t == self.max_t-1:
            output_message = '100 % completed'
            self._colored_output(output_message, 32)
        #print self.t



class RICHARDS_1D_ENKF(RICHARDS_1D):
    """
    This is the main class of the Ensemble Kalman Filter (EnKF)
    coupled with the one dimensional unsaturated model based on the 
    RICHARDS equation. The model is given in the class RICHARDS_1D.
        
    This will read the input data,
    do the processing
    and then write the output files
    
    """
    
    def __init__(self,input_file):
        """
        Input:
            input_file: the file which contains all the information
            including forcing and parameters.
        """      
        self.input_file = input_file
        self.n_ens = 10
        # read the input data
        self._read_input()
        
        # initialize the variables and output file
        self.initialize()
        
        ################ run the model ########################
        for t in range(self.max_t):
            self.t = t
              
            # get forcing data at current time step        
            self._get_forcing()
            
            # perturb the soil par ensemble
            self._perturb_soil_par_ens()
                        
            # call the unsat module with ensemble
            for ens in range(self.n_ens):
                self.ens = ens
                
                self._unsat_ens()
                
            # ensemble kalmfan filter
            self._enkf_par()

            
            self._write_output()                
                
                
        self.nc_file.close() # close the output file


    def _enkf(self):
        """
        ensemble kalman filter
        """
        # compute the covariance matrix of the state+par
        x = self.theta_ens
        x_bar = np.tile(x.mean(axis=0),(10,1))
        x_x_bar = x-x_bar
        cov_xx = np.dot(x_x_bar.T,x_x_bar)        
        
        # get the measurement of the ssm at the current time
        # and generate its ensemble and compute its covariance matrix
        e = np.zeros((self.n_ens, self.no_layer))
        e[:,0] = self.theta_ens[:,0] - self.meas_ssm[self.t]
        e = e + 0.02*np.random.normal(size=(self.n_ens,self.no_layer))
        cov_ee = np.dot(e.T, e)  
        
        # compute kalaman gain
        K = np.dot(cov_xx,np.linalg.pinv(cov_xx+cov_ee))
        
        # update the measurment
        d = np.zeros(self.no_layer)
        usm = np.zeros((self.n_ens,self.no_layer))
             
        for ens in range(self.n_ens):
            d[0] = self.meas_ssm[self.t] - x[ens,0]
            usm[ens,:] = (x[ens,:] + np.dot(K,d))
               
        self.theta_ens = usm
    
    def _enkf_par(self):
        """
        ensemble kalman filter
        """
        # make the state vector which contains the soil moisture at different 
        #depths and soil parameters
        x = self.theta_ens
        thetar = self.soil_par_ens['thetar']
        thetas = self.soil_par_ens['thetas']
        alpha = self.soil_par_ens['alpha']
        n = self.soil_par_ens['n']
        Ks = self.soil_par_ens['Ks']
        l = self.soil_par_ens['l']
        soil_par = (np.vstack([thetar, thetas, alpha, n, Ks, l])).T
        X = np.hstack([x, soil_par])
        
        # compute the covariance matrix of the state+par
        X_bar = np.tile(X.mean(axis=0),(10,1))
        X_X_bar = X-X_bar
        cov_XX = np.dot(X_X_bar.T,X_X_bar)        
        
        # get the measurement of the ssm at the current time
        # and generate its ensemble and compute its covariance matrix
        e = np.zeros((self.n_ens, self.no_layer+6))
        e[:,0] = self.theta_ens[:,0] - self.meas_ssm[self.t]
        e = e + 0.02*np.random.normal(size=(self.n_ens,self.no_layer+6))
        cov_ee = np.dot(e.T, e)  
        
        # compute kalaman gain
        K = np.dot(cov_XX,np.linalg.pinv(cov_XX+cov_ee+1e-6*np.eye(self.no_layer+6)))
        
        # update the measurment
        d = np.zeros(self.no_layer+6)
        usm_par = np.zeros((self.n_ens,self.no_layer+6))
             
        for ens in range(self.n_ens):
            d[0] = self.meas_ssm[self.t] - x[ens,0]
            usm_par[ens,:] = (X[ens,:] + np.dot(K,d))
        
        # check for the range of the updated ensemble
        # soil moisture
        theta_ens = usm_par[:,:self.no_layer]
        theta_ens[theta_ens<0] = 0
        theta_ens[theta_ens>1] = 1
        self.theta_ens = theta_ens
        # soil parameters
        thetar = usm_par[:,self.no_layer+0]
        thetas = usm_par[:,self.no_layer+1]
        alpha = usm_par[:,self.no_layer+2]
        n = usm_par[:,self.no_layer+3]
        Ks = usm_par[:,self.no_layer+4]
        l = usm_par[:,self.no_layer+5]
        
        thetar[thetar < self.thetar1] = self.thetar1
        thetas[thetas < self.thetas1] = self.thetas1
        alpha[alpha < self.alpha1] = self.alpha1
        n[n < self.n1] = self.n1
        Ks[Ks < self.Ks1] = self.Ks1
        l[l < self.l1] = self.l1
        
        thetar[thetar > self.thetar2] = self.thetar2
        thetas[thetas > self.thetas2] = self.thetas2
        alpha[alpha > self.alpha2] = self.alpha2
        n[n > self.n2] = self.n2
        Ks[Ks > self.Ks2] = self.Ks2
        l[l > self.l2] = self.l2
        
        self.soil_par_ens['thetar'] = thetar
        self.soil_par_ens['thetas'] = thetas
        self.soil_par_ens['alpha'] = alpha
        self.soil_par_ens['n'] = n
        self.soil_par_ens['Ks'] = Ks
        self.soil_par_ens['l'] = l
        
        self.K = K
        
        

    def initialize(self):
        """
        this initializes all the required variables
        and open the netcdf file for writting
        also generates the initial ensemble of the soil hydraulic parameters
        """
        max_t = int(self.final_time/self.dt_flux)
        #max_t = 56
        self.max_t = max_t
        self.iter_dt = 1
                        
        # open file for writing
        file = nc.NetCDFFile(self.ofile_name, 'w')
        setattr(file, 'title', 'output of the model ambhas.richards')
        now = datetime.datetime.now()
        setattr(file, 'description', 'The model was run at %s'%(now.ctime()))
        file.createDimension('depth', self.no_layer)
        file.createDimension('time', self.max_t+1)
        file.createDimension('ensemble', self.n_ens)
        
        # depth
        varDims = 'depth',
        depth = file.createVariable('depth', 'd', varDims)
        depth.units = 'm'
        depth[:] = np.tile(self.dz,self.no_layer).cumsum()-self.dz/2
        
        # time (year and doy)
        varDims = 'time',
        self.nc_year = file.createVariable('year', 'd', varDims)
        self.nc_doy = file.createVariable('doy', 'd', varDims)
        
        # soil moisture
        varDims = 'ensemble', 'depth', 'time'
        self.nc_sm = file.createVariable('sm','d', varDims)
        self.nc_sm.units = 'v/v'
        self.nc_sm[:,:,0] = self.theta_ens
        
        # recharge and aet
        varDims = 'time',
        self.nc_aet = file.createVariable('aet','d',varDims)
        self.nc_aet.units = 'mm'
        self.nc_recharge = file.createVariable('recharge','d',varDims)
        self.nc_recharge.units = 'mm'

        # recharge and aet
        varDims = 'ensemble','time'
        self.nc_thetar = file.createVariable('thetar','d',varDims)
        self.nc_thetar.units = 'v/v'
        self.nc_thetas = file.createVariable('thetas','d',varDims)
        self.nc_thetas.units = 'v/v'    
        self.nc_alpha = file.createVariable('alpha','d',varDims)
        self.nc_alpha.units = '1/m'
        self.nc_n = file.createVariable('n','d',varDims)
        self.nc_n.units = '-' 
        self.nc_Ks = file.createVariable('Ks','d',varDims)
        self.nc_Ks.units = 'm/s'
        self.nc_l = file.createVariable('l','d',varDims)
        self.nc_l.units = '-' 
        
        self.nc_file = file
        
        # generate soil hydraulic parameters
        self._generate_soil_par_ens()

    def _read_input(self):
        """
        This checks if all the required input sheets are present in the xls file,
        read the data from input file, which can be used later in other functions
        """
        
        # list of required files in the input directory
        input_sheets = ['ind', 'forcing', 'initial_condition', 'units', 'temporal_info',
                       'spatial_info', 'soil_hyd_par_ens', 'output_par']
        
        # check if all the required sheets are present or not
        self._check_sheets(input_sheets, self.input_file)
        
        # read the legend
        self._read_ind()
        
        # read the spatial data
        self._read_spatial()
        
        # read the temporal data
        self._read_temporal()

        # read the units 
        self._read_units()
        
        # read the initial condition
        self._read_initial_condition()
        
        # read the ensemble information for the shp
        self._read_shp_ens()
        
        # read the forcing infomation
        self._read_forcing()
        
        # read the outfile name
        self._read_ofile_name()
        
        # read the measured data
        self._read_measured() 
        
        # print the reading status
        output_message = 'Input data reading completed sucessfully'
        self._colored_output(output_message, 32)
        
    def _read_measured(self):
        """
        read the measured surface soil moisture (ssm) data
        """
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_name('forcing')
        
        data_len = sheet.nrows-1
        meas_ssm = np.zeros(data_len)
        j = self.ind['meas_sm']
        
        for i in xrange(data_len):
            meas_ssm[i] = sheet.cell_value(i+1,3+j)
                    
        self.meas_ssm = meas_ssm
    
    def _read_initial_condition(self):
        """
        read initial condition
        """
        #get the row number from the ind
        j = self.ind['initial_condition']
        
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_name('initial_condition')
        theta_0 = sheet.cell_value(j,1)
        self.theta_ens = np.tile(theta_0,(self.n_ens,self.no_layer))    
    
    def _read_shp_ens(self):
        """
        read the information about the ensemble of the soil hydraulic parameters
        the information being read is the min, max, perturbation factore (%)
        """
        #get the row number from the ind
        j = self.ind['soil_hyd_par_ens']
        
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_name('soil_hyd_par_ens')
        shp_ens = {}
        shp_ens['thetar'] = sheet.cell_value(j,1), sheet.cell_value(j,7)
        shp_ens['thetas'] = sheet.cell_value(j,2), sheet.cell_value(j,8)
        shp_ens['alpha']  = sheet.cell_value(j,3), sheet.cell_value(j,9)
        shp_ens['n']      = sheet.cell_value(j,4), sheet.cell_value(j,10)
        shp_ens['Ks']     = sheet.cell_value(j,5), sheet.cell_value(j,11)
        shp_ens['l']      = sheet.cell_value(j,6), sheet.cell_value(j,12)
                
        self.shp_ens = shp_ens
    
    
    def _generate_soil_par_ens(self):
        """
        this uses the LHS to generate the ensemble of the parameters
        
        this also computes the perturbation needed to perturb the parameters
        which is done in another function
        """
        # i means min, 2 means maximum
        thetar1, thetar2 = self.shp_ens['thetar']
        thetas1, thetas2 = self.shp_ens['thetas']
        alpha1, alpha2 = self.shp_ens['alpha']
        n1, n2 = self.shp_ens['n']
        l1, l2 = self.shp_ens['l']
        Ks1, Ks2 = self.shp_ens['Ks']
        self.thetar1 = thetar1; self.thetar2 = thetar2 
        self.thetas1 = thetas1; self.thetas2 = thetas2  
        self.alpha1 = alpha1; self.alpha2 = alpha2  
        self.n1 = n1; self.n2 = n2  
        self.Ks1 = Ks1; self.Ks2 = Ks2  
        self.l1 = l1; self.l2 = l2  
        
        v = lhs(stats.uniform,[],siz=(self.n_ens,6))
        soil_par_ens = {}
        soil_par_ens['thetar'] = thetar1 + (thetar2-thetar1)*v[:,0]
        soil_par_ens['thetas'] = thetas1 + (thetas2-thetas1)*v[:,1]
        soil_par_ens['alpha'] = alpha1 + (alpha2-alpha1)*v[:,2]
        soil_par_ens['n'] = n1 + (n2-n1)*v[:,3]
        soil_par_ens['l'] = l1 + (l2-l1)*v[:,4]
        # for KS it is log-uniform
        log_Ks1 = np.log10(Ks1)
        log_Ks2 = np.log10(Ks2)
        soil_par_ens['Ks'] = 10**(log_Ks1 + (log_Ks2-log_Ks1)*v[:,5])
        #soil_par_ens['Ks'] = Ks1 + (Ks2-Ks1)*v[:,5]
        
        self.soil_par_ens = soil_par_ens
        
        #perturbation parameter
        soil_pert = {}
        soil_pert['thetar'] = (thetar2-thetar1)*0.5/100.0
        soil_pert['thetas'] = (thetas2-thetas1)*0.5/100.0
        soil_pert['alpha'] =  (alpha2-alpha1)*0.5/100.0
        soil_pert['n'] =      (n2-n1)*0.5/100.0
        soil_pert['l'] =      (l2-l1)*0.5/100.0
        #soil_pert['Ks'] = 10**(log_Ks1 + (log_Ks2-log_Ks1)*0.01/100.0)
        soil_pert['Ks'] = (Ks2-Ks1)*0.5/100.0
        self.soil_pert = soil_pert

    def _perturb_soil_par_ens(self):
        """
        this functions perturb the soil hydraulic parameters 
        using the gaussian random variables
        """
        v = np.random.normal(size=(self.n_ens,6))
        
        soil_par_ens = {}
        soil_par_ens['thetar'] = self.soil_par_ens['thetar']+self.soil_pert['thetar']*v[:,0]
        soil_par_ens['thetas'] = self.soil_par_ens['thetas']+self.soil_pert['thetas']*v[:,1]
        soil_par_ens['alpha'] = self.soil_par_ens['alpha']+self.soil_pert['alpha']*v[:,2]
        soil_par_ens['n'] = self.soil_par_ens['n']+self.soil_pert['n']*v[:,3]
        soil_par_ens['l'] = self.soil_par_ens['l']+self.soil_pert['l']*v[:,4]
        soil_par_ens['Ks'] = self.soil_par_ens['Ks']+self.soil_pert['Ks']*v[:,5]
        
        self.soil_par_ens = soil_par_ens

    
    def _unsat_ens(self):
        """
        top boundary: atmoshpheric
        bottom boundary: gravity drainage
        """
        ens = self.ens
        thetar = self.soil_par_ens['thetar'][ens]
        thetas = self.soil_par_ens['thetas'][ens]
        alpha = self.soil_par_ens['alpha'][ens]
        n = self.soil_par_ens['n'][ens]
        l = self.soil_par_ens['l'][ens]
        Ks = self.soil_par_ens['Ks'][ens]
        m = 1-1/n
        nz = self.no_layer
        evap_0 = thetar+0.25*(thetas-thetar)
        evap_1 = thetar+0.75*(thetas-thetar)
        
        # read the soil moisture from the ensemble
        theta = 1.0*self.theta_ens[ens]
        
        #delta_theta = (np.abs(flux)).max()
        
        iter_dt = max(24,int(np.ceil(self.rain_cur*self.dt_flux*1000/0.15)))
        self.iter_dt = int(max(iter_dt,0.75*self.iter_dt))
        
        #if self.t == 56:
        #    self.iter_dt = int(self.iter_dt*6)
        #print self.iter_dt
        
        recharge_day = 0
        aet_day = 0
        
        # check for time step
        for i in range(self.iter_dt):
            dt = self.dt_flux/self.iter_dt
            #print dt
            # top boundary value
            smi = (theta[0]-evap_0)/(evap_1-evap_0)
            if smi<0: smi=0
            if smi>1: smi=1
            aet = smi*self.pet_cur
            Bvalue = self.rain_cur-aet
        
            K = self.theta2kr(theta,thetar,thetas,m,l,Ks)
            smc = self.smcf(theta,thetar,thetas,alpha,m,n)
            psi = self.theta2psi(theta,thetar,thetas,m,n,alpha)
            
            
            #flux boundary condition at the top
            Kmid = np.empty(nz+1)        
            Kmid[0] = 0
            for i in range(1,nz):
                Kmid[i] = 0.5*(K[i]+K[i-1])
            Kmid[nz] = K[nz-1]
            
            #Setting the coefficient for the internal nodes
            A = np.empty(nz)
            B = np.empty(nz)
            C = np.empty(nz)
            D = np.empty(nz)
            dz = self.dz
            dz2 = dz**2
            
            for i in range(nz):
                A[i] = -(Kmid[i]/dz2)
                B[i] = smc[i]/dt+(Kmid[i+1]+Kmid[i])/dz2
                C[i] = A[i]
                D[i] = smc[i]*psi[i]/dt-(Kmid[i+1]-Kmid[i])/dz
            # setting the coefficient for the top bc (flux boundary)
            i = 0        
            A[0] = 0
            B[0] = smc[i]/dt+(Kmid[1])/dz2
            D[0] = smc[i]*psi[i]/dt+(Bvalue-Kmid[1])/dz
            
            # setting the coefficient for the bottom bc: gravity drainage
            B[nz-1] = smc[nz-1]/dt+(Kmid[nz])/dz2
            C[nz-1] = 0
            D[nz-1] = smc[nz-1]*psi[nz-1]/dt-(Kmid[nz]-Kmid[nz-1])/dz
            
            # Solving using the thomas algorithm
            beta = np.empty(nz)
            gamma = np.empty(nz)
            u = np.empty(nz)
            beta[0] = B[0]
            gamma[0] = D[0]/beta[0]
            for i in range(1,nz):
                beta[i] = B[i]-(A[i]*C[i-1])/(beta[i-1])
                gamma[i] = (D[i]-A[i]*gamma[i-1])/(beta[i])
            
            u[nz-1] = gamma[nz-1]
            for i in range(nz-2,-1,-1):
                u[i] = gamma[i]-(C[i]*u[i+1])/beta[i]
            
            # flux computation between nodes
            J = np.empty(nz+1)
            for i in range(1,nz):
                J[i] = Kmid[i]*(1-(u[i]-u[i-1])/dz)
            J[0] = Bvalue
            J[nz] = Kmid[nz]
            
            J[nz] = J[nz]
            # flux updating
            flux = np.diff(J)*dt/dz
            theta = theta - flux
            
            theta[theta>thetas] = 0.99*thetas
            theta[theta<thetar] = 1.01*thetar
                        
            aet_day += aet*dt 
            recharge_day += J[nz]*dt           
            
                            
        self.theta_ens[ens] = theta        
        
    def _write_output(self):
        """
        this functions writes the output at each time step
        """
        # write the output
        self.nc_year[self.t] = (self.cur_year)
        self.nc_doy[self.t] = (self.cur_doy)
        self.nc_sm[:,:,self.t+1] = self.theta_ens
        #self.nc_recharge[self.t] = recharge_day
        #self.nc_aet[self.t] = aet_day
        self.nc_thetar[:,self.t] = self.soil_par_ens['thetar']
        self.nc_thetas[:,self.t] = self.soil_par_ens['thetas']
        self.nc_alpha[:,self.t] = self.soil_par_ens['alpha']
        self.nc_n[:,self.t] = self.soil_par_ens['n']
        self.nc_Ks[:,self.t] = self.soil_par_ens['Ks']
        self.nc_l[:,self.t] = self.soil_par_ens['l']
        
if __name__=='__main__':
     
    #maddur = RICHARDS_1D('/home/tomer/richards/input/maddur.xls')
    #output_file = nc.NetCDFFile(maddur.ofile_name, 'r')
    #print output_file.variables
    #foo = output_file.variables['sm']
    #theta= foo.getValue()
    #print theta[:,-2]
    #print theta[:,-1]
    #plt.plot(theta[:,-1]); plt.plot(theta[:,-2]); plt.show()
    
    maddur_ens = RICHARDS_1D_ENKF('/home/tomer/richards/input/maddur_ens.xls')
    #output_file = nc.NetCDFFile(maddur_ens.ofile_name, 'r')
    #foo = output_file.variables['sm'][:,0,:]
    
    