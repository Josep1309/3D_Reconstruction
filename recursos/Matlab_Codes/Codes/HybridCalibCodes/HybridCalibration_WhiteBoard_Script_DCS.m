close all
addpath('StereoCalibCodes')


%%%%%%%%%% Load calibration parameters
% These were obtained with the Python calibration code
pathExp   = '23-03-22 - Pruebas';
pathSteCalib = 'Estereo';
pathPhases = 'WhiteBoardExt';

StereoCalibNom = 'Estereo_TSC_0_2';
StereoType = 'MT'; % 'BT'



load(['..\Data\',pathExp,'\',pathPhases,'\',pathPhases,'_PhasesData.mat'])
load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'.mat']);


nPoses = StereoParams.NumPatterns; % Number of calibration poses

% Camera and projector resolutions
m_imageWidth = 1936;        %1936   %1280 ;     %2048
m_imageHeight = 1464;       %1464   %1024 ;     %1536
m_projectorWidth =  912;    %912    %1280;      %912
m_projectorHeight = 1140;   %1140   %800;       %1140

% Fringe features: patterns period and shifts
FringePitch = 18; NStep = 18; NBits = 7;
%%
MaskC([1:15 end-15:end],:,:) = 0;
MaskC(:,[1:15 end-15:end],:) = 0;

[Fxa ,Fya ,Maskx ,Masky ] = CleanPhase(Fx, Fy,MaskC>0,1); %  5th order 2D-polynomial
Indi = NaN.*Maskx; Indi(MaskC>0) = 1;



%% R3D by Stereo model + Reg


[erms,dist,Dx_ip, Dy_ip, Dz_ip, Dx_rp, Dy_rp, Dz_rp,errDis] = XYZ_R3D_Target(StereoParams,StereoType,Fxa,Fya,FringePitch,Indi>0,'Fy',Indi>0);
% [erms,dist,Dx_ip, Dy_ip, Dz_ip, Dx_rp, Dy_rp, Dz_rp,errDis] = XYZ_R3D_Target(StereoParams,StereoType,Fxa(:,:,1),Fya(:,:,1),FringePitch,Indi(:,:,1)>0,'Fy');

% [Xs,Ys,Zs] = StereoReconstruction(Fxa,Fya,MaskC,18,StereoParams,3,'Fy');


%%

a = [50 50];
index = logical(0*(1:16)); index(4:12) = 1;
degreePol = 2:5; 

indexZ = (Dz_ip>300).*(Dz_ip<800);
Indi = Indi.*NaN; Indi(indexZ>0) = 1;

[coefx_i,ex_i,N3_i,ermsx]  = Polyfit3D(Fya(:,:,index).*Indi(:,:,index),Dx_ip(:,:,index).*Indi(:,:,index),a,degreePol); % Regresion de fase Vs X
[coefy_i,ey_i,N3_i,ermsy]  = Polyfit3D(Fya(:,:,index).*Indi(:,:,index),Dy_ip(:,:,index).*Indi(:,:,index),a,degreePol); % Regresion de fase Vs Y
[coefz_i,ez_i,N3_i,ermsz]  = Polyfit3D(Fya(:,:,index).*Indi(:,:,index),Dz_ip(:,:,index).*Indi(:,:,index),a,degreePol); % Regresion de fase Vs Z

Lip_ei = min(Fya,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_ei = max(Fya,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión
%% Generacion de graficas de los polinomios de Fase Vs Z de diferentes grados

y = figure(90); hold off
y2 = figure(93); hold off
% a =  [1030,45];
a =  [600,600];
% a =  [478,990];
meanerr = {};
indexx = find(shiftdim(indexZ(a(1),a(2),:)));
indexx = 4:12;

for i = 1:numel(degreePol)
    X_e = Eval_PhaseRegression(coefx_i{i}, Fya);
    Y_e = Eval_PhaseRegression(coefy_i{i}, Fya);
    Z_e = Eval_PhaseRegression(coefz_i{i}, Fya);
    
    err = sqrt((X_e-Dx_ip).^2+(Y_e-Dy_ip).^2+(Z_e-Dz_ip).^2);
    meanerr{i} = shiftdim(mean(err,[1 2],'omitnan'));
    zmean{i} =   shiftdim(mean(Z_e,[1 2],'omitnan'));

    figure(90); plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Z_e(a(1),a(2),:)),'-','LineWidth',1.5),    hold on
    figure(93); plot(zmean{i}, meanerr{i},'*-','LineWidth',1.5),    hold on
%     figure, imagesc(Z_e(:,:,1))

end

figure(90)
plot(shiftdim(  Fya(a(1),a(2),indexx)), ...
     shiftdim(Dz_ip(a(1),a(2),indexx)),'or')
plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_ip(a(1),a(2),:)),'-*m','MarkerSize',7)



% pgon = polyshape([155 155 280 280],[520 720 720 520]);
% ypol = plot(pgon);
% ypol.EdgeAlpha = 0;
% ypol.FaceAlpha = 0.1;

legend('POL2','POL3','POL4','POL5','Regression Points','Experimental Curve','Calibration range')
% legend('Experimental Curve','Regression Points','POL2','POL3','POL4','POL5')
hold off

grid on
xlabel('Phase [rad]')
ylabel('Z - Depth [mm]')
y.Children(1).FontSize = 10;
y.Children(2).FontSize = 12;
ylim([400 830])
% xlim([100 280])

figure(93)
legend('POL2','POL3','POL4','POL5')
grid on
xlabel('Z - Depth [mm]')
ylabel('RMS error [mm]')
y2.Children(1).FontSize = 10;
y2.Children(2).FontSize = 12;
ylim([0 10])
%% Save Regression-hybrid Data

for i = 1:4
    coefx = coefx_i{i}; coefy = coefy_i{i}; coefz = coefz_i{i};
    ex = ex_i{i}; ey = ey_i{i}; ez = ez_i{i}; N3 = N3_i{i};
    Lip = Lip_ei; Lsp = Lsp_ei;
    nomHybrid = ['HybPol',num2str(i+1),'_520-720'];
    direc = ['..\Data\',pathExp,'\',pathPhases,'\',StereoCalibNom,'_',nomHybrid,'_Fa.mat'];
    % save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
    save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')
end

