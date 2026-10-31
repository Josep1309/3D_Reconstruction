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
m_imageWidth = 1600;        %1936   %1280 ;     %2048
m_imageHeight = 1200;       %1464   %1024 ;     %1536
m_projectorWidth =  912;    %912    %1280;      %912
m_projectorHeight = 1140;   %1140   %800;       %1140

% Fringe features: patterns period and shifts
FringePitch = 18; NStep = 18; NBits = 7;
%%
MaskC([1:15 end-15:end],:,:) = 0;
MaskC(:,[1:15 end-15:end],:) = 0;

[Fxa ,Fya ,Maskx ,Masky ] = CleanPhase(Fx, Fy,MaskC>0,1); %  5th order 2D-polynomial
Indi = NaN.*MaskC; Indi(MaskC>0) = 1;



%% R3D by Stereo model + Reg


Fxa = Fx;
Fya = Fy;
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
a =  [50,50];
indexx = find(shiftdim(indexZ(a(1),a(2),:)));
indexx = 4:12;

for i = 1:numel(degreePol)
    Z_e = Eval_PhaseRegression(coefz_i{i}, Fya);
    plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Z_e(a(1),a(2),:)),'-','LineWidth',1.5)
    hold on
end

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
% ylim([200 830])
% xlim([100 280])

%% Save Regression-hybrid Data

for i = 1:4
    coefx = coefx_i{i}; coefy = coefy_i{i}; coefz = coefz_i{i};
    ex = ex_i{i}; ey = ey_i{i}; ez = ez_i{i}; N3 = N3_i{i};
    Lip = Lip_ei; Lsp = Lsp_ei;
    nomHybrid = 'HybPol3_520-720';
    direc = ['..\Data\',pathExp,'\',pathPhases,'\',StereoCalibNom,'_',nomHybrid,'_Fa.mat'];
    % save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
    save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')
end
%%
nVirtualplanes = 7;
Rv = repmat([1 0 0;0 1 0;0 0 1],[1,1,nVirtualplanes]);
tv = repmat([0;0;0],[1 nVirtualplanes]);
% tv(3,:) = [350, 800]; % Planes' distances from the camera
tv(3,:) = [571,596,627,655,679,700,727]; % Planes' distances from the camera

[Dx_v,Dy_v,Dz_v,Up_v,Vp_v] = BackPropagation_Planes2(StereoParams,StereoType,Rv,tv,[m_imageHeight m_imageWidth],1);

TPhx_v = Up_v*(2*pi)/FringePitch; % Virtual plane Phases
TPhy_v = Vp_v*(2*pi)/FringePitch;


%%  Hybrid rational con ITERACION
Indeex = 1:14;

indexZ = (Dz_rp<300)+(Dz_rp>1000);
Mask = Dx_rp*0+1;
cb = 15;
Mask([1:cb end-cb:end],:,:) = NaN;
Mask(:,[1:cb end-cb:end],:) = NaN;
Mask(find(indexZ)) = NaN;

aa = [500, 500];

[coefx_eit,coefy_eit,coefz_eit,erms,F1] = HybridIterativeOpt(Dx_rp(:,:,Indeex),Dy_rp(:,:,Indeex),Dz_rp(:,:,Indeex),Fya(:,:,Indeex),Mask(:,:,Indeex)>0,4,aa);
[coefx_eit2,coefy_eit2,coefz_eit2,erms2] = HybridIterativeOpt(Dx_v,Dy_v,Dz_v,Fya(:,:,Indeex),Mask(:,:,Indeex)>0,5,aa);

N_eit= sum(Mask(:,:,Indeex)>0,3);


Lip_eit = min(Fya,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_eit = max(Fya,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión
%% Save Iterative

coefx = coefx_eit; coefy = coefy_eit; coefz = coefz_eit;
% ex = ex_i{4}; ey = ey_i{4}; ez = ez_i{4}; 
N3 = N_eit;
Lip = Lip_eit; Lsp = Lsp_eit;
nomHybrid = 'HybFracWB2_ite';
direc = ['..\Data\',pathExp,'\',pathPhases,'\',StereoCalibNom,'_',nomHybrid,'_Fa.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')




%%
a =  [600,800];
Z_e = Eval_PhaseFrac(coefz_if, Fya);

% figure,
hold on
% plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_ip(a(1),a(2),:)),'om'), hold on
plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Z_e(a(1),a(2),:)),'-r')


%%
figure(90),
a = [20 20];
plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_ip(a(1),a(2),:)),'om'), hold on
kk = 0;
for i = 3:16
    kk = kk+1;
    index = (1:i)+8-round(i/2);
    [coefz_if,ez_if]     = Racionalfit3D(Fya  (:,:,index).*Indi(:,:,index), Dz_ip(:,:,index),[],1);
    Z_e = Eval_PhaseFrac(coefz_if, Fya);
    
    ex =(Dz_ip - Z_e);
    e(:,:,kk) = sqrt(sum((ex).^2,3,'omitnan')./sum(~isnan(ex),3));

    plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Z_e(a(1),a(2),:)))
    drawnow
end

legend(['datos', string(3:16)])

%%
mues = 10;
Maskis = 0*(~isnan(coefz_if));
Maskis(1:mues:end,1:mues:end,:) = ~isnan(coefz_if(1:mues:end,1:mues:end,:));
[Dz5th,FX] =  PhaseAdj5(coefz_if(:,:,:),Maskis,5,1,[],5);

%%

coee = 2;
figure, imagesc(100*((-Dz5th(:,:,coee)+coefz_if(:,:,coee))./coefz_if(:,:,coee)).*Indi(:,:,3)), colorbar



