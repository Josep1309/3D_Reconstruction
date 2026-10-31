pathExp   = '23-03-01 - Pruebas';
pathSteCalib = 'Estereo';
StereoCalibNom = 'Estereo_TSC_0_3';


load(['..\Data\',pathExp,'\',pathSteCalib,'\',pathSteCalib,'_PhasesData.mat'],'Fya','Indi')


load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_DataForRegression.mat'], ...
   'Dx','Dy','Dz','Dx_ip','Dy_ip','Dz_ip','Dx_rp','Dy_rp','Dz_rp','Dx_v','Dy_v',"Dz_v",'TPhy_v')






[coefx_e,ex_e,N3_e]     = Polyfit3D(Dz(:,:,Index3).*Indi(:,:,Index3),Dy(:,:,Index3),a,1); % Regresion de fase Vs X
[coefz_e,ez_e   ]       = Polyfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dz(:,:,Index3),a,3); % Regresion de fase Vs Z


[coefz_e,ez_e   ]       = Polyfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dz_ip(:,:,Index3),a,5); % Regresion de fase Vs Z



[coefz_ev,ez_ev   ]     = Polyfit3D(Phy_ev,Dz_ev,a,3); % Regresion de fase Vs Z
[coefz_iv,ez_iv   ]     = Polyfit3D(Phy_ev,Dz_iv,a,3); % Regresion de fase Vs Z


% [coefz_i,ez_i,]         = Polyfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dz_ip(:,:,Index3),[51 24],3); % Regresion de fase Vs Z
%%


Index3 = shiftdim(sum(Indi,[1 2],'omitnan'))>1910000;


[coefx_f,ex_f,N] = Polyfit3D(Dz_ip(:,:,Index3).*Indi(:,:,Index3), Dx_ip(:,:,Index3),[500 500],2);
[coefy_f,ey_f]   = Polyfit3D(Dz_ip(:,:,Index3).*Indi(:,:,Index3), Dy_ip(:,:,Index3),[500 500],2);
[coefz_f,ez_f]   = Racionalfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dz_ip(:,:,Index3),[500 500],1);







%%




