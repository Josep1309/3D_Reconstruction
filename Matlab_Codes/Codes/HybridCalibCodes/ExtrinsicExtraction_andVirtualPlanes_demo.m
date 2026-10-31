
close all
addpath('StereoCalibCodes')


%%%%%%%%%% Load calibration parameters
% These were obtained with the Python calibration code
pathExp   = '23-03-07 - Pruebas';
pathSteCalib = 'Estereo';
StereoCalibNom = 'Estereo_TSC_0_2';
StereoType = 'MT'; % 'BT'
% StereoCalibNom = 'Ste_R0C11000P00000S00';
% StereoCalibNom = 'Ste_R0C11111P11111S00';



% load(['..\Data\',pathExp,'\',pathSteCalib,'\',pathSteCalib,'_TSC_0_3.mat']);

load(['..\Data\',pathExp,'\',pathSteCalib,'\',pathSteCalib,'_PhasesData.mat'],'Fxa','Fya','Indi','MaskP')

if(strcmp(StereoType,'BT'))
    StereoParams = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'.mat']);
%     ve = [1:2 4 5:15 16 17 18 20];
    ve = [1:4 6 9:24 26:30] ;

    Fxa = Fxa(:,:,ve);
    Fya = Fya(:,:,ve);
%     Fy = Fy(:,:,ve);
%     Fx = Fx(:,:,ve);
    Indi = Indi(:,:,ve);
else
    load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'.mat']);
end



nPoses = StereoParams.NumPatterns; % Number of calibration poses

% Camera and projector resolutions
m_imageWidth = 1600;        %1936   %1280 ;     %2048
m_imageHeight = 1200;       %1464   %1024 ;     %1536
m_projectorWidth =  912;    %912    %1280;      %912
m_projectorHeight = 1140;   %1140   %800;       %1140

% Fringe features: patterns period and shifts
FringePitch = 18; NStep = 18; NBits = 7;
%% Generacion de grafica de calibración estereo

gg = figure(900); hold off
gg.Position = [403   219   590   447];
figExt = showExtrinsics(StereoParams);
% figExt.Position = [0.1300    0.1100    0.7750    0.8150];
for i = 1:numel(figExt.Children)

    if(strcmp(figExt.Children(i).Type,'patch'))
        figExt.Children(i-1).Visible = 'off';
        
%         figExt.Children(i).FaceColor = 'r';
%         figExt.Children(i).EdgeColor = 'r';
    end
    rotate(figExt.Children(i), [0 1 0], -90)
end
hold on,

[zcub,ycub] = meshgrid(500:200:700,-300:600:300);

gcub = surf(ycub,zcub,ycub*0+75); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3;  gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
gcub = surf(ycub*0+130,zcub,ycub); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;


[zcub,ycub] = meshgrid(701:100:801,-300:600:300);
gcub = surf(ycub,zcub,ycub*0+75); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
gcub = surf(ycub*0+130,zcub,ycub); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;


[zcub,ycub] = meshgrid(399:100:499,-300:600:300);
gcub = surf(ycub,zcub,ycub*0+75); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;
gcub = surf(ycub*0+130,zcub,ycub); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;


figExt.Title.Visible = 'off';
figExt.XLabel.Visible = 'off';
figExt.YLabel.Visible = 'off';
figExt.ZLabel.Visible = 'off';

zlim([-180 75])
xlim([-100 130])
figExt.DataAspectRatio = [1 1.5 1];
figExt.XTickLabel = flipud(figExt.XTickLabel);
figExt.FontSize = 11;
exportgraphics(figure(900),'StereoCalib-Extrinsics.png','Resolution',500)

%% 

focalLength = StereoParams.fc_left;
principalPoint = StereoParams.cc_left;
imageSize = [m_imageHeight m_imageWidth];
cameraParams = cameraIntrinsics(focalLength,principalPoint,imageSize,'RadialDistortion',StereoParams.kc_left([1 2 5]),'TangentialDistortion',StereoParams.kc_left([3 4]));


patternSize = [16, 21];         % [7, 21]
centerDistance = 10;            % 20
Pattern_type = 'symmetric';     % asymmetric
worldPoints = generateCircleGridPoints(patternSize,centerDistance,'PatternType', Pattern_type);
%  worldPoints = (worldPoints/15).*[15.0588 14.9090];

RR =[]; tt =[];
ii=0;
for i =ve
    ii=ii+1;
    [worldOrientation,worldLocation] = estimateWorldCameraPose(M(:,:,i,1),[worldPoints worldPoints(:,1)*0],cameraParams);
    RR(:,:,ii) = worldOrientation;
    tt(:,ii) = -worldOrientation*worldLocation';
end


[Dxa,Dya,Dza,Upa,Vpa] = BackPropagation_Planes2(StereoParams,StereoType,RR,tt,[m_imageHeight m_imageWidth],0);


%% Estimate 3D coordinates of the target using the Extrinsic parameters obtained by StereoCalib
% Method Proposed by Zhang
%

% Page transpose to transpose all pages of R(:,:,nPoses)
if(isfield(StereoParams,'RotationMatrices'))
    R = StereoParams.RotationMatrices;
    t = StereoParams.TranslationVectors;
else
    R = pagetranspose(StereoParams.CameraParameters1.RotationMatrices);
    t = StereoParams.CameraParameters1.TranslationVectors';
end

[Dx,Dy,Dz,Up,Vp] = BackPropagation_Planes2(StereoParams,StereoType,R,t,[m_imageHeight m_imageWidth],0);
TPhx = Up*(2*pi)/FringePitch; % 
TPhy = Vp*(2*pi)/FringePitch;

%% Create Virtual planes

nVirtualplanes = 2;
Rv = repmat([1 0 0;0 1 0;0 0 1],[1,1,nVirtualplanes]);
tv = repmat([0;0;0],[1 nVirtualplanes]);
% tv(3,:) = [350, 800]; % Planes' distances from the camera
tv(3,:) = [400, 850]; % Planes' distances from the camera

[Dx_v,Dy_v,Dz_v,Up_v,Vp_v] = BackPropagation_Planes2(StereoParams,StereoType,Rv,tv,[m_imageHeight m_imageWidth],0);

TPhx_v = Up_v*(2*pi)/FringePitch; % Virtual plane Phases
TPhy_v = Vp_v*(2*pi)/FringePitch;

%% Estimate 3D coordinates adjusting the points to a plane
% Initial Hybrid Calibration 
%
% Indifit = MaskP;
% MaskFit = MaskP*0+1;
% Indifit = MaskFit.*maskrec;
% [erms,dist,Dx_ip, Dy_ip, Dz_ip] = XYZ_R3D_Target(StereoParams,StereoType,Fxa,Fya,FringePitch,Indi>0,'Fy');
[erms,dist,Dx_ip, Dy_ip, Dz_ip, Dx_rp, Dy_rp, Dz_rp,errDis] = XYZ_R3D_Target(StereoParams,StereoType,Fxa,Fya,FringePitch,Indi>0,'Fy',Indi>0);


% save(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_DataForRegression.mat'], ...
%      'Fya','Dx','Dy','Dz','Dx_ip','Dy_ip','Dz_ip','Dx_rp','Dy_rp','Dz_rp','Dx_v','Dy_v',"Dz_v",'TPhy_v')
% save(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_DataForRegression.mat'],'-append','Indi')
%%
planN = 1;
figure, imagesc(errDis(:,:,planN).*Indi(:,:,planN)), caxis([-1 1])
aux = errDis(:,:,planN); 
figure, histogram(aux(Indi(:,:,planN)>0),-1:0.02:1)
%% Regression Fy Vs coordinates 5th order
a = [97 1208];

% Using extrinsic positioning 

Index3 = shiftdim(sum(Indi,[1 2],'omitnan'))>900000; 

degreePol = 3; 

[coefx_e,ex_e,N3_e]     = Polyfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dx(:,:,Index3),a,degreePol); % Regresion de fase Vs X
[coefy_e,ey_e   ]       = Polyfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dy(:,:,Index3),a,degreePol); % Regresion de fase Vs Y
[coefz_e,ez_e   ]       = Polyfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dz(:,:,Index3),a,degreePol); % Regresion de fase Vs Z


[coefx_i,ex_i,N3_i]     = Polyfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dx_ip(:,:,Index3),a,degreePol); % Regresion de fase Vs X
[coefy_i,ey_i   ]       = Polyfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dy_ip(:,:,Index3),a,degreePol); % Regresion de fase Vs Y
[coefz_i,ez_i,]         = Polyfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dz_ip(:,:,Index3),a,degreePol); % Regresion de fase Vs Z

Lip_ei = min(Fya,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_ei = max(Fya,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión
%% Fraccional model



[coefx_ef,ex_ef,N_f] = Polyfit3D(Dz(:,:,Index3).*Indi(:,:,Index3), Dx(:,:,Index3),[500 500],1);
[coefy_ef,ey_ef]     = Polyfit3D(Dz(:,:,Index3).*Indi(:,:,Index3), Dy(:,:,Index3),[500 500],1);
[coefz_ef,ez_ef]     = Racionalfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dz(:,:,Index3),[500 500],1);



[coefx_if,ex_if,N_f] = Polyfit3D(Dz_ip(:,:,Index3).*Indi(:,:,Index3), Dx_ip(:,:,Index3),[600 800],1);
[coefy_if,ey_if]     = Polyfit3D(Dz_ip(:,:,Index3).*Indi(:,:,Index3), Dy_ip(:,:,Index3),[600 800],1);
% [coefx_if,ex_if,N_f]     = Racionalfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dx_ip(:,:,Index3),[663 796],1);
% [coefy_if,ey_if]     = Racionalfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dy_ip(:,:,Index3),[600 800],1);
[coefz_if,ez_if]     = Racionalfit3D(Dz_rp(:,:,Index3).*Indi(:,:,Index3),Fxa(:,:,Index3),[600 800],1);



Lip_ei = min(Fya,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_ei = max(Fya,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión
%% Generate figure with Error fitting


cx = 482 ; cy =1053;


germs = figure(90); 

sp1 = subplot(3,2,1); imagesc(ez_if.*Indi(:,:,1)), caxis([0 0.15]), 
% germs.Children.FontSize = 12;
xlabel('u [Pixel]');
ylabel('v [Pixel]');
title('\Phi Vs Z');
axis equal
xlim([0 1600])
ylim([0 1200])
cb = colorbar;
% c.Location = ''    
cb.Label.String = 'mm';
cb.FontSize = 10;

% g1 = drawpoint;

% cx = round(g1.Position(2)); cy = round(g1.Position(1));

x = shiftdim(Fya(cx,cy,:)); y = shiftdim(Dz_ip(cx,cy,:));
sp2 =  subplot(3,2,2); hold off,
x2 = sort(x);
a = coefz_if(:,:,1);  b = coefz_if(:,:,2);  
c = coefz_if(:,:,3);  d = coefz_if(:,:,4); 
fy = (a(cx,cy) + b(cx,cy)*x2)./(1+c(cx,cy)*x2+d(cx,cy).*x2.*x2); 
plot(x2,fy,'Linewidth',1.5), hold on
plot(x,y,'*','MarkerSize',6)
xlabel(' Phase [rad]')
ylabel(' Z [mm]')
grid on
% sp2.XLim = [230 271];


leg1 = legend(['Z =  $ \frac{',num2str(round(a(cx,cy),2)),'+',num2str(round(b(cx,cy),3)),'\phi}{1',num2str(round(c(cx,cy),3)),'\phi}$'],'Data','Interpreter','latex');
% text(235,600,sprintf('$$ Y = \frac{%4.3f + %4.3f \phi}{1+%4.3f\phi} $$',a(cx,cy),b(cx,cy),c(cx,cy)),'Interpreter','latex')
% sp2.Position(3) = sp1.Position(3)*0.7; 
% sp2.Position(3) = sp1.Position(3)*0.7; 
leg1.FontSize = 10;
leg1.Box = 'off';

sp3 = subplot(3,2,3); imagesc(ex_if.*Indi(:,:,1)), caxis([0 0.15]), 
xlabel('u [Pixel]');
ylabel('v [Pixel]');
title('Z Vs X');
axis equal
xlim([0 1600])
ylim([0 1200])
cb =colorbar;
cb.Label.String = 'mm';
cb.FontSize = 10;


x = shiftdim(Dz_ip(cx,cy,:)); y = shiftdim(Dx_ip(cx,cy,:));

sp4 = subplot(3,2,4); hold off,
x2 = sort(x);
a = coefx_if(:,:,1);  b = coefx_if(:,:,2);  
fy = (a(cx,cy)*x2 + b(cx,cy)); 
plot(x2,fy,'Linewidth',1.5), hold on
plot(x,y,'*','MarkerSize',6)
xlabel(' Z [mm]')
ylabel(' X [mm]')
grid on
leg2 = legend(['X =',num2str(round(a(cx,cy),3)),'Z + ' num2str(round(b(cx,cy),3))],'Data','Interpreter','latex');
leg2.FontSize = 10;
leg2.Box = 'off';
% fg.Children.FontSize = 12;
% legend('Data',sprintf('X =  %4.3f Z + %4.3f',a(cx,cy)),b(cx,cy))



sp5 = subplot(3,2,5); imagesc(ey_if.*Indi(:,:,1)), caxis([0 0.15]), 
xlabel('u [Pixel]');
ylabel('v [Pixel]');
title('Z Vs Y');
axis equal
xlim([0 1600])
ylim([0 1200])
cb =colorbar;
cb.Label.String = 'mm';
cb.FontSize = 10;

x = shiftdim(Dz_ip(cx,cy,:)); y = shiftdim(Dy_ip(cx,cy,:));
sp6 = subplot(3,2,6); hold off,
x2 = sort(x);
a = coefy_if(:,:,1);  b = coefy_if(:,:,2);  
fy = (a(cx,cy)*x2 + b(cx,cy)); 
plot(x2,fy,'Linewidth',1.5), hold on
plot(x,y,'*','MarkerSize',6)
xlabel(' Z [mm]')
ylabel(' Y [mm]')
grid on
leg3 = legend(['Y = ',num2str(round(a(cx,cy),3)),'Z + ' num2str(round(b(cx,cy),3))],'Data','Interpreter','latex');
leg3.FontSize = 10;
leg3.Box = 'off';
% legend('Data',sprintf('Y =  %4.3f Z + %4.3f',a(cx,cy)),b(cx,cy))

% fg.Children.FontSize = 12;


sp4.Position(3) = sp4.Position(3)*0.7; 
sp6.Position(3) = sp6.Position(3)*0.7; 
sp2.Position(3) = sp2.Position(3)*0.7; 

% sp3.Position(2) = sp3.Position(2)*1.5; 
% sp4.Position(2) = sp4.Position(2)*1.5; 
% sp5.Position(2) = sp5.Position(2)*1.5; 
% sp6.Position(2) = sp6.Position(2)*1.5; 
% sp4.XLim = [542.5864 691];
% sp6.XLim = [542.5864 691];

sp1.FontSize = 11;
sp2.FontSize = 11;
sp3.FontSize = 11;
sp4.FontSize = 11;
sp5.FontSize = 11;
sp6.FontSize = 11;


%% Regresion Fy Vs coodinates including virtual planes

Phy_ev = cat(3,Fya(:,:,Index3).*Indi(:,:,Index3),TPhy_v); 
Dx_ev   = cat(3,Dx(:,:,Index3),Dx_v);  Dx_iv   = cat(3,Dx_ip(:,:,Index3),Dx_v); 
Dy_ev   = cat(3,Dy(:,:,Index3),Dy_v);  Dy_iv   = cat(3,Dy_ip(:,:,Index3),Dy_v);  
Dz_ev   = cat(3,Dz(:,:,Index3),Dz_v);  Dz_iv   = cat(3,Dz_ip(:,:,Index3),Dz_v);

[coefx_ev,ex_ev,N3_ev]  = Polyfit3D(Phy_ev,Dx_ev,a,degreePol); % Regresion de fase Vs X
[coefy_ev,ey_ev   ]     = Polyfit3D(Phy_ev,Dy_ev,a,degreePol); % Regresion de fase Vs Y
[coefz_ev,ez_ev   ]     = Polyfit3D(Phy_ev,Dz_ev,a,degreePol); % Regresion de fase Vs Z


[coefx_iv,ex_iv,N3_iv]  = Polyfit3D(Phy_ev,Dx_iv,a,degreePol); % Regresion de fase Vs X
[coefy_iv,ey_iv   ]     = Polyfit3D(Phy_ev,Dy_iv,a,degreePol); % Regresion de fase Vs Y
[coefz_iv,ez_iv   ]     = Polyfit3D(Phy_ev,Dz_iv,a,degreePol); % Regresion de fase Vs Z


Lip_v = min(Phy_ev,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_v = max(Phy_ev,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión


%% Save Regression-hybrid Data

coefx = coefx_e; coefy = coefy_e; coefz = coefz_e; N3 = N3_e;
% ex = ex_e; ey = ey_e; ez = ez_e; 
Lip = Lip_ei; Lsp = Lsp_ei;
nomHybrid = '1';
direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid',num2str(degreePol),'_',nomHybrid,'_Fa.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

disp(['Guardado ...'])

coefx = coefx_i; coefy = coefy_i; coefz = coefz_i;N3 = N3_i;
% ex = ex_i; ey = ey_i; ez = ez_i; 
Lip = Lip_ei; Lsp = Lsp_ei;
nomHybrid = '2';
direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid',num2str(degreePol),'_',nomHybrid,'_Fa.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

disp(['Guardado ...'])

coefx = coefx_ev; coefy = coefy_ev; coefz = coefz_ev;N3 = N3_ev;
% ex = ex_ev; ey = ey_ev; ez = ez_ev; 
Lip = Lip_v; Lsp = Lsp_v;
nomHybrid = ['1v_', num2str(nVirtualplanes)];
direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid',num2str(degreePol),'_',nomHybrid,'_Fa.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

disp(['Guardado ...'])

coefx = coefx_iv; coefy = coefy_iv; coefz = coefz_iv;  N3 = N3_iv; 
% ex = ex_iv; ey = ey_iv; ez = ez_iv; 
Lip = Lip_v; Lsp = Lsp_v;
nomHybrid = ['2v_', num2str(nVirtualplanes)];
direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid',num2str(degreePol),'_',nomHybrid,'_Fa.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

disp(['Guardado ...'])


%% Save Hybrid Fraccionary
degreePol = 1;
coefx = coefx_ef; coefy = coefy_ef; coefz = coefz_ef;N3 = N_f;
% ex = ex_ev; ey = ey_ev; ez = ez_ev; 
Lip = Lip_ei; Lsp = Lsp_ei;
nomHybrid = '1frac';
direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid',num2str(degreePol),'_',nomHybrid,'_Fa.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

disp(['Guardado ...'])
%%
coefx = coefx_if; coefy = coefy_if; coefz = coefz_if;  N3 = N_f; 
% ex = ex_iv; ey = ey_iv; ez = ez_iv; 
Lip = Lip_ei; Lsp = Lsp_ei;
nomHybrid = '2frac';
direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid',num2str(degreePol),'_',nomHybrid,'_FracXYZ.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

disp(['Guardado ...'])




%% Using only experimental data

Ermsx = sqrt(sum((ex_e.*Indi).^2,3,'omitnan')./sum(Indi>0,3,'omitnan'));
Ermsy = sqrt(sum((ey_e.*Indi).^2,3,'omitnan')./sum(Indi>0,3,'omitnan'));
Ermsz = sqrt(sum((ez_e.*Indi).^2,3,'omitnan')./sum(Indi>0,3,'omitnan'));

Indi2 = N3_e*NaN; Indi2(N3_e>6) = 1;

figure(500), imagesc(Ermsx.*Indi2), caxis([0 0.2]), title(['Order ',num2str(degreePol), ' degree polynomial fit error - Ph Vs X '])
figure(501), imagesc(Ermsy.*Indi2), caxis([0 0.2]), title(['Order ',num2str(degreePol), ' degree polynomial fit error - Ph Vs Y '])
figure(502), imagesc(Ermsz.*Indi2), caxis([0 1]), title(['Order ',num2str(degreePol), ' degree polynomial fit error - Ph Vs Z '])


%% adding the virtual planes

Indiv = cat(3,Indi,Indi(:,:,1:2)*0+1);

Ermsx = ex_iv;
Ermsy = ey_iv;
Ermsz = ez_iv;

Indi2 = N3_e*NaN; Indi2(N3_e>7) = 1;

figure(500), imagesc(Ermsx.*Indi2), caxis([-0.2 0.2]), title('5th degree polynomial fit error - Ph Vs X ')
figure(501), imagesc(Ermsy.*Indi2), caxis([-0.2 0.2]), title('5th degree polynomial fit error - Ph Vs Y ')
figure(502), imagesc(Ermsz.*Indi2), caxis([-1 1]), title('5th degree polynomial fit error - Ph Vs Z ')

%%

ndatos = 30;
Re  = repmat(reshape(linspace(0,1,ndatos),[1 1 ndatos]),size(TPhy_v(:,:,1)));
Reg = (TPhy_v(:,:,end)-TPhy_v(:,:,1)).*Re+ TPhy_v(:,:,1);


Z_e = Eval_PhaseRegression(coefz_e, Reg);
Z_i = Eval_PhaseRegression(coefz_i, Reg);
% Z_ev = Eval_PhaseRegression(coefz_ev, Reg);
% Z_iv = Eval_PhaseRegression(coefz_iv, Reg);
Z_if = Eval_PhaseFrac(coefz_if, Reg);
Z_ef = Eval_PhaseFrac(coefz_ef, Reg);

direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_EvalPolinomios_3orden_Fa.mat'];
save(direc,'Z_e','Z_i','Z_if','Z_ef','Dz_ip','Dz_v','TPhy_v','Fya','Reg')


% save(direc,'coefz_e','coefz_i','coefz_ev','coefz_iv','Dz_rp','Dz_v','TPhy_v','Fya')
% 
% save(direc,'Reg','-append')


%%
aa = [275,275;
    1200,11;
    275, 1740;
    1175,1500
    750, 950];
a = aa(4,:);
linew = 1.3;
figure(5), hold off, 
%         plot(shiftdim(Reg(a(1),a(2),:)), shiftdim(Z_e(a(1),a(2),:)),'-b','LineWidth',linew), hold on, 
        plot(shiftdim(Reg(a(1),a(2),:)), shiftdim(Z_i(a(1),a(2),:)),'-r','LineWidth',linew ) , hold on
%         plot(shiftdim(Reg(a(1),a(2),:)), shiftdim(Z_ev(a(1),a(2),:)),'-y','LineWidth',linew )
%         plot(shiftdim(Reg(a(1),a(2),:)), shiftdim(Z_iv(a(1),a(2),:)),'--g','LineWidth',linew )
        plot(shiftdim(Reg(a(1),a(2),:)), shiftdim(Z_if(a(1),a(2),:)),'--k','LineWidth',linew )
% plot(shiftdim(Reg(a(1),a(2),:)), shiftdim(ZZ_e2(a(1),a(2),:)) )

plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_ip(a(1),a(2),:)),'om')
% plot(shiftdim(TPhy_v(a(1),a(2),:)), shiftdim(Dz_v(a(1),a(2),:)),'ok')
title(['pixel (', num2str(a(1)),',', num2str(a(2)),')'])
% legend('Method 1','Method 2','Method 1 - Virtual','Method 2 - Virtual','Method frac','Experimental points','Virtual points')
legend('POL3','Rational proposed','Experimental points')
% legend('Traditional Regression','Extended Regression','Experimental points','Virtual points')
% legend('Traditional Regression','Extended Regression','Extended Regression 2','Experimental points','Virtual points')

% pause()
% savefig(figure(5),sprintf('RegressionsPix(%d,%d)-VP%d-Ord%d.fig',a(1),a(2),nVirtualplanes,degreePol))
% saveas(figure(5),sprintf('RegressionsPix(%d,%d)-VP%d-Ord%d_6vp.png',a(1),a(2),nVirtualplanes,degreePol),'png')
%% Show phase errors
% Ind = mask*NaN; Ind(mask) =1; 
for k=15
    DPH = (Fya(:,:,k)-TPhy(:,:,k));
    Maski = Indi(:,:,k)>0;
    rms_phase(k) = rms(DPH(Maski(:)));
    figure(50+4), imagesc(DPH.*Indi(:,:,k)), caxis([-1.5 1.5])
%     figure(50+4), imagesc((Fx(:,:,k)-TPhx(:,:,k))), caxis([-1.5 1.5])
    figure(100+4), imagesc(Images(:,:,k))
end
%% Compare Theorical Vs Experimental phases

pixel = [500,500];
figure,  plot(shiftdim(TPhy(pixel(1),pixel(2),:)),shiftdim(Dz(pixel(1),pixel(2),:)),'*r'), 
hold on, plot(shiftdim(Fy(pixel(1),pixel(2),:)),shiftdim(Dz(pixel(1),pixel(2),:)),'*b')
xlabel('Phase [rad]')
ylabel('Z [mm]')
legend('Theorical','Experimental')

