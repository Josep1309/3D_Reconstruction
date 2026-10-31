%%  Lectura de la información de calibración
close all
addpath('StereoCalibCodes')


%%%%%%%%%% Load calibration parameters
% These were obtained with the Python calibration code
pathExp   = 'Pruebas-24-05-14';
pathSteCalib = 'Estereo';
StereoCalibNom = 'Estereo_TSC_0_2';
StereoType = 'MT'; % 'BT'
% StereoCalibNom = 'Ste_R0C11000P00000S00';
% StereoCalibNom = 'Ste_R0C11111P11111S00';


load(['..\Data\',pathExp,'\',pathSteCalib,'\',pathSteCalib,'_PhasesData.mat'],'Fxa','Fya','Fy','Indi','MaskP')

if(strcmp(StereoType,'BT'))
    StereoParams = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'.mat']);
else
    load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'.mat']);
end



nPoses = StereoParams.NumPatterns; % Number of calibration poses

% Camera and projector resolutions
m_imageWidth = 1024;        %1936   %1280 ;     %2048
m_imageHeight = 800;       %1464   %1024 ;     %1536
m_projectorWidth =  912;    %912    %1280;      %912
m_projectorHeight = 1140;   %1140   %800;       %1140

% Fringe features: patterns period and shifts
FringePitch = 18; NStep = 18; NBits = 7;
%% Generacion de grafica de calibración estereo
% Esa seccion es solamente utilizada para generar el esquema estereo del
% sistema utilizando los parametros de calibración. 
%

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
% exportgraphics(figure(900),'StereoCalib-Extrinsics.png','Resolution',500)
%% Estimate 3D coordinates adjusting the points to a plane

[erms_s,dist,Dx_ip, Dy_ip, Dz_ip, Dx_rp, Dy_rp, Dz_rp,errDis] = XYZ_R3D_Target(StereoParams,StereoType,Fxa,Fya,FringePitch,Indi>0,'Fy',Indi>0);

%% Regresion entre las coordenadas de los puntos corregidos y las fases ajustadas

Index3 = 1:7;
[coefx_if,ex_if,N_if] = Polyfit3D(Dz_ip(:,:,Index3).*Indi(:,:,Index3), Dx_ip(:,:,Index3),[600 800],1);
[coefy_if,ey_if]     = Polyfit3D(Dz_ip(:,:,Index3).*Indi(:,:,Index3), Dy_ip(:,:,Index3),[600 800],1);
% [coefz_if,ez_if]     = Racionalfit3D(Fya(:,:,Index3).*Indi(:,:,Index3),Dz_ip(:,:,Index3),[600 800],1);

[coefz_if,ez_if]     = RacionalfitXY_3D(Fxa(:,:,Index3).*Indi(:,:,Index3), ...
                                        Fya(:,:,Index3).*Indi(:,:,Index3), ...
                                        Dz_ip(:,:,Index3),[600 800]);


Lip_ei = min(Fya,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_ei = max(Fya,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión

%%  Regresion entre las coordenadas de los puntos corregidos y las fases ajustadas  con ITERACION
Indeex = [1:10 12:25];
Mask = MaskP*0+1;
cb = 15;
Mask([1:cb end-cb:end],:,:) = 0;
Mask(:,[1:cb end-cb:end],:) = 0;

aa = [];

[coefx_it,coefy_it,coefz_it,erms_it] = HybridIterativeOpt(Dx_rp(:,:,Indeex),Dy_rp(:,:,Indeex),Dz_rp(:,:,Indeex),Fya(:,:,Indeex),Mask(:,:,Indeex)>0,7,aa);

N_it= sum(Mask(:,:,Indeex)>0,3);


Lip_it = min(Fya,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_it = max(Fya,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión


%%  Regresion entre las coordenadas de los puntos corregidos y las fases ajustadas  con ITERACION
Indeex = [1:10 12:25];
Mask = Dx*0+1;
cb = 15;
Mask([1:cb end-cb:end],:,:) = 0;
Mask(:,[1:cb end-cb:end],:) = 0;

aa = [];
Dx = Dx+Dx_rp*0; Dy = Dy+Dx_rp*0; Dz = Dz+Dx_rp*0;
[coefx_eit,coefy_eit,coefz_eit,erms_eit] = HybridIterativeOpt(Dx(:,:,Indeex),Dy(:,:,Indeex),Dz(:,:,Indeex),Fya(:,:,Indeex)+Dx_rp(:,:,Indeex)*0,Mask(:,:,Indeex)>0,5,aa);

N_eit= sum(Mask(:,:,Indeex)>0,3);


Lip_eit = min(Fya,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_eit = max(Fya,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión



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


sp1.FontSize = 11;
sp2.FontSize = 11;
sp3.FontSize = 11;
sp4.FontSize = 11;
sp5.FontSize = 11;
sp6.FontSize = 11;


%% Save Hybrid information

coefx = coefx_if; coefy = coefy_if; coefz = coefz_if;  N3 = N_if; 
% ex = ex_iv; ey = ey_iv; ez = ez_iv; 
Lip = Lip_ei; Lsp = Lsp_ei;
nomHybrid = 'prueba';
direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid_',nomHybrid,'_FracXYZ.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

disp(['Guardado ...'])

%% Save Hybrid information ITERATIVE

coefx = coefx_it; coefy = coefy_it; coefz = coefz_it;  N3 = N_it; 
% ex = ex_iv; ey = ey_iv; ez = ez_iv; 
Lip = Lip_it; Lsp = Lsp_it;
nomHybrid = 'prueba';
direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid_',nomHybrid,'_FracXYZ_ite.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

disp(['Guardado ...'])

%% Save Hybrid information ITERATIVE

coefx = coefx_eit; coefy = coefy_eit; coefz = coefz_eit;  N3 = N_eit; 
% ex = ex_iv; ey = ey_iv; ez = ez_iv; 
Lip = Lip_eit; Lsp = Lsp_eit;
nomHybrid = 'prueba';
direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid_',nomHybrid,'_FracXYZ_iteExt.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

disp(['Guardado ...'])







