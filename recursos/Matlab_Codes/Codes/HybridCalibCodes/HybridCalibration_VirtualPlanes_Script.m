
close all
addpath('StereoCalibCodes')


%%%%%%%%%% Load calibration parameters
% These were obtained with the Python calibration code
pathExp   = '23-03-22 - Pruebas';
pathSteCalib = 'Estereo';
StereoCalibNom = 'Estereo_TSC_0_2';
StereoType = 'MT'; % 'BT'


load(['..\Data\',pathExp,'\',pathSteCalib,'\',pathSteCalib,'_PhasesData.mat'],'Fxa','Fya','Indi','MaskP')

if(strcmp(StereoType,'BT'))
    StereoParams = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'.mat']);
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

D0 = 419;
D1 = 520; D2 = 720;
D3 = 821;

[zcub,ycub] = meshgrid(D1:200:D2,-300:600:300);

gcub = surf(ycub,zcub,ycub*0+75); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3;  gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
gcub = surf(ycub*0+130,zcub,ycub); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;


[zcub,ycub] = meshgrid((D2+1):100:D3,-300:600:300);
gcub = surf(ycub,zcub,ycub*0+75); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
gcub = surf(ycub*0+130,zcub,ycub); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;


[zcub,ycub] = meshgrid(D0:100:(D1-1),-300:600:300);
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
% exportgraphics(figure(2),'StereoCalib-Extrinsics.png','Resolution',500)


%% Create Virtual planes for mapping

nVirtualplanes = 9;
Rv = repmat([1 0 0;0 1 0;0 0 1],[1,1,nVirtualplanes]);
tv = repmat([0;0;0],[1 nVirtualplanes]);
% tv(3,:) = [350, 800]; % Planes' distances from the camera
tv(3,:) = linspace(525, 725, nVirtualplanes); % Planes' distances from the camera

[Dx_v,Dy_v,Dz_v,Up_v,Vp_v] = BackPropagation_Planes2(StereoParams,StereoType,Rv,tv,[m_imageHeight m_imageWidth],1);

TPhx_v = Up_v*(2*pi)/FringePitch; % Virtual plane Phases
TPhy_v = Vp_v*(2*pi)/FringePitch;

%% Regression Fy Vs Virtual coordinates 3rd order
a = [];

% Using extrinsic positioning 
degreePol = 4; 

[coefx_v,ex_v,N3_v,ermsx]     = Polyfit3D(TPhy_v,Dx_v,a,degreePol); % Regresion de fase Vs X
[coefy_v,ey_v,N3_v,ermsy]       = Polyfit3D(TPhy_v,Dy_v,a,degreePol); % Regresion de fase Vs Y
[coefz_v,ez_v,N3_v,ermsz]       = Polyfit3D(TPhy_v,Dz_v,a,degreePol); % Regresion de fase Vs Z

Lip_v = min(TPhy_v,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_v = max(TPhy_v,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión




%% Generate figure with Error fitting


cx = 482 ; cy =1053;


germs = figure(90); 

sp1 = subplot(3,1,1); imagesc(ez_v.*Indi(:,:,1)), caxis([0 0.15]), 
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

% x = shiftdim(Fya(cx,cy,:)); y = shiftdim(Dz_ip(cx,cy,:));
% sp2 =  subplot(3,2,2); hold off,
% x2 = sort(x);
% a = coefz_if(:,:,1);  b = coefz_if(:,:,2);  
% c = coefz_if(:,:,3);  d = coefz_if(:,:,4); 
% fy = (a(cx,cy) + b(cx,cy)*x2)./(1+c(cx,cy)*x2+d(cx,cy).*x2.*x2); 
% plot(x2,fy,'Linewidth',1.5), hold on
% plot(x,y,'*','MarkerSize',6)
% xlabel(' Phase [rad]')
% ylabel(' Z [mm]')
% grid on
% sp2.XLim = [230 271];
% leg1 = legend(['Z =  $ \frac{',num2str(round(a(cx,cy),2)),'+',num2str(round(b(cx,cy),3)),'\phi}{1',num2str(round(c(cx,cy),3)),'\phi}$'],'Data','Interpreter','latex');
% text(235,600,sprintf('$$ Y = \frac{%4.3f + %4.3f \phi}{1+%4.3f\phi} $$',a(cx,cy),b(cx,cy),c(cx,cy)),'Interpreter','latex')
% sp2.Position(3) = sp1.Position(3)*0.7; 
% sp2.Position(3) = sp1.Position(3)*0.7; 
% leg1.FontSize = 10;
% leg1.Box = 'off';


sp3 = subplot(3,1,2); imagesc(ex_v.*Indi(:,:,1)), caxis([0 0.15]), 
xlabel('u [Pixel]');
ylabel('v [Pixel]');
title('Z Vs X');
axis equal
xlim([0 1600])
ylim([0 1200])
cb =colorbar;
cb.Label.String = 'mm';
cb.FontSize = 10;


% x = shiftdim(Dz_ip(cx,cy,:)); y = shiftdim(Dx_ip(cx,cy,:));
% sp4 = subplot(3,2,4); hold off,
% x2 = sort(x);
% a = coefx_if(:,:,1);  b = coefx_if(:,:,2);  
% fy = (a(cx,cy)*x2 + b(cx,cy)); 
% plot(x2,fy,'Linewidth',1.5), hold on
% plot(x,y,'*','MarkerSize',6)
% xlabel(' Z [mm]')
% ylabel(' X [mm]')
% grid on
% leg2 = legend(['X =',num2str(round(a(cx,cy),3)),'Z + ' num2str(round(b(cx,cy),3))],'Data','Interpreter','latex');
% leg2.FontSize = 10;
% leg2.Box = 'off';
% fg.Children.FontSize = 12;
% legend('Data',sprintf('X =  %4.3f Z + %4.3f',a(cx,cy)),b(cx,cy))



sp5 = subplot(3,1,3); imagesc(ey_v.*Indi(:,:,1)), caxis([0 0.15]), 
xlabel('u [Pixel]');
ylabel('v [Pixel]');
title('Z Vs Y');
axis equal
xlim([0 1600])
ylim([0 1200])
cb =colorbar;
cb.Label.String = 'mm';
cb.FontSize = 10;

% x = shiftdim(Dz_ip(cx,cy,:)); y = shiftdim(Dy_ip(cx,cy,:));
% sp6 = subplot(3,2,6); hold off,
% x2 = sort(x);
% a = coefy_if(:,:,1);  b = coefy_if(:,:,2);  
% fy = (a(cx,cy)*x2 + b(cx,cy)); 
% plot(x2,fy,'Linewidth',1.5), hold on
% plot(x,y,'*','MarkerSize',6)
% xlabel(' Z [mm]')
% ylabel(' Y [mm]')
% grid on
% leg3 = legend(['Y = ',num2str(round(a(cx,cy),3)),'Z + ' num2str(round(b(cx,cy),3))],'Data','Interpreter','latex');
% leg3.FontSize = 10;
% leg3.Box = 'off';
% legend('Data',sprintf('Y =  %4.3f Z + %4.3f',a(cx,cy)),b(cx,cy))

% fg.Children.FontSize = 12;


% sp4.Position(3) = sp4.Position(3)*0.7; 
% sp6.Position(3) = sp6.Position(3)*0.7; 
% sp2.Position(3) = sp2.Position(3)*0.7; 


sp1.FontSize = 11;
% sp2.FontSize = 11;
sp3.FontSize = 11;
% sp4.FontSize = 11;
sp5.FontSize = 11;
% sp6.FontSize = 11;



%% Viartual planes extended to limits  

nVirtualplanes2 = 17;
Rv2 = repmat([1 0 0;0 1 0;0 0 1],[1,1,nVirtualplanes2]);
tv2 = repmat([0;0;0],[1 nVirtualplanes2]);
% tv(3,:) = [350, 800]; % Planes' distances from the camera
tv2(3,:) = linspace(425, 825, nVirtualplanes2); % Planes' distances from the camera

[Dx_v2,Dy_v2,Dz_v2,Up_v2,Vp_v2] = BackPropagation_Planes2(StereoParams,StereoType,Rv2,tv2,[m_imageHeight m_imageWidth],1);

TPhx_v2 = Up_v2*(2*pi)/FringePitch; % Virtual plane Phases
TPhy_v2 = Vp_v2*(2*pi)/FringePitch;


%%
Fya = TPhy_v2; Fx = TPhx_v2;
Fy = TPhy_v2;  Fxa = TPhx_v2;
Indi = ~isnan(TPhy_v2);
Mask = Indi;


save(['..\Data\',pathExp,'\',pathSteCalib,'\',pathSteCalib,'_PhasesData_virtual.mat'],'Fx','Fy','Fxa','Fya','Indi','Mask')

disp(" Finalizado ")

% Z_v = Eval_PhaseRegression(coefz_v, TPhy_v2);
%%



gg = figure(2);

gg.Position = [403   219   590   447];
figExt = gg.Children(2);
% figExt.Position = [0.1300    0.1100    0.7750    0.8150];
cols =[];
for i = 1:numel(figExt.Children)

    if(strcmp(figExt.Children(i).Type,'patch'))
        figExt.Children(i-1).Visible = 'off';
        figExt.Children(i).Visible = 'off';
        cols = [cols; figExt.Children(i).FaceColor];
%         figExt.Children(i).FaceColor = 'r';
%         figExt.Children(i).EdgeColor = 'r';
    end
    rotate(figExt.Children(i), [0 1 0], -90)
end
hold on,

D0 = 419;
D1 = 520; D2 = 720;
D3 = 821;
ly = 200;
lx = 200;

[zcub,ycub] = meshgrid(D1:200:D2,-300:600:300);

gcub = surf(ycub,zcub,ycub*0+ly); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3;  gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
gcub = surf(ycub*0+lx,zcub,ycub); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;


[zcub,ycub] = meshgrid((D2+1):100:D3,-300:600:300);
gcub = surf(ycub,zcub,ycub*0+ly); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
gcub = surf(ycub*0+lx,zcub,ycub); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;


[zcub,ycub] = meshgrid(D0:100:(D1-1),-300:600:300);
gcub = surf(ycub,zcub,ycub*0+ly); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;
gcub = surf(ycub*0+lx,zcub,ycub); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;


figExt.Title.Visible = 'off';
figExt.XLabel.Visible = 'off';
figExt.YLabel.Visible = 'off';
figExt.ZLabel.Visible = 'off';

zlim([-220 200])
xlim([-200 200])
figExt.DataAspectRatio = [1 1 1];
figExt.XTickLabel = flipud(figExt.XTickLabel);
figExt.FontSize = 11;
exportgraphics(figure(2),'VirtualSampling-Extrinsics.png','Resolution',500)

%%

y = figure(90); hold off
a =  [600,50];



for i = 1:numel(degreePol)
    Z_e = Eval_PhaseRegression(coefz_v{i}, TPhy_v2);
    plot(shiftdim(TPhy_v2(a(1),a(2),:)), shiftdim(Z_e(a(1),a(2),:)),'-','LineWidth',1.5)
    hold on
end


plot(shiftdim(TPhy_v(a(1),a(2),:)), shiftdim(Dz_v(a(1),a(2),:)),'or','MarkerSize',7), 
plot(shiftdim(TPhy_v2(a(1),a(2),:)), shiftdim(Dz_v2(a(1),a(2),:)),'-*m')



pgon = polyshape([155 155 280 280],[520 720 720 520]);
ypol = plot(pgon);
ypol.EdgeAlpha = 0;
ypol.FaceAlpha = 0.1;
legend('POL2','POL3','POL4','POL5','Selected Points','Stereo','Calibration range')

hold off

grid on
xlabel('Phase [rad]')
ylabel('Z - Depth [mm]')
y.Children(1).FontSize = 10;
y.Children(2).FontSize = 12;
% ylim([300 830])
% xlim([60 280])

%% Para X

y = figure(90); hold off
a =  [1200,1200];



clear Z_e

for i = 1:numel(degreePol)
    X_e{i} = Eval_PhaseRegression(coefx_v{i}, TPhy_v2);
    Y_e{i} = Eval_PhaseRegression(coefy_v{i}, TPhy_v2);
    Z_e{i} = Eval_PhaseRegression(coefz_v{i}, TPhy_v2);
    
    errx{i} = Dx_v2 - X_e{i};
    erry{i} = Dy_v2 - Y_e{i};
    errz{i} = Dz_v2 - Z_e{i};
    i
end

%%
plot(shiftdim(TPhy_v(a(1),a(2),:)), shiftdim(Dx_v(a(1),a(2),:)),'or','MarkerSize',7), 
plot(shiftdim(TPhy_v2(a(1),a(2),:)), shiftdim(Dx_v2(a(1),a(2),:)),'-*m')



% pgon = polyshape([155 155 280 280],[520 720 720 520]);
% ypol = plot(pgon);
% ypol.EdgeAlpha = 0;
% ypol.FaceAlpha = 0.1;
legend('POL2','POL3','POL4','POL5','Selected Points','Stereo','Calibration range')

hold off

grid on
xlabel('Phase [rad]')
ylabel('Z - Depth [mm]')
y.Children(1).FontSize = 10;
y.Children(2).FontSize = 12;
% ylim([300 830])
% xlim([60 280])


%
%%
y = figure(91); hold off
a =  [600,600];


for i = 1:numel(degreePol)
    Z_e = Eval_PhaseRegression(coefz_v{i}, TPhy_v2);
    plot(shiftdim(Z_e(a(1),a(2),:)), shiftdim(Z_e(a(1),a(2),:)-Dz_v2(a(1),a(2),:)),'-','LineWidth',1.5)
    hold on
end


% plot(shiftdim(TPhy_v(a(1),a(2),:)), shiftdim(Dz_v(a(1),a(2),:)),'or','MarkerSize',7), 
% plot(shiftdim(TPhy_v2(a(1),a(2),:)), shiftdim(Dz_v2(a(1),a(2),:)-Dz_v2(a(1),a(2),:)),'-*m')

pgon = polyshape([520 720 720 520],[-20 -20 30 30]);
ypol = plot(pgon,'FaceColor',[0.6350    0.0780    0.1840]);
ypol.EdgeAlpha = 0;
ypol.FaceAlpha = 0.1;
% legend('POL2','POL3','POL4','POL5','Selected Points','Stereo','Calibration range')

legend('POL2','POL3','POL4','POL5','Selected Points','Stereo')

hold off

grid on
xlabel('Z - Depth [mm]')
ylabel('Error [mm]')
y.Children(1).FontSize = 10;
y.Children(2).FontSize = 12;
% xlim([300 830])
% ylim([-20 30])



%% Save Regression-hybrid Data


coefx = coefx_v; coefy = coefy_v; coefz = coefz_v;  N3 = N3_v; 
% ex = ex_iv; ey = ey_iv; ez = ez_iv; 
Lip = Lip_v; Lsp = Lsp_v;
nomHybrid = ['_HybPol',num2str(degreePol),'_Virt_520-720-9'];
direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,nomHybrid,'.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

disp(['Guardado ...'])






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


%% Generate figure with Error fitting

cx = 482 ; cy =1053;

germs = figure(90); 
sp1 = subplot(3,2,1); imagesc(ez_v), caxis([0 0.15]), 
xlabel('u [Pixel]'); ylabel('v [Pixel]'); title('\Phi Vs Z');
axis equal, xlim([0 1600]), ylim([0 1200])
cb = colorbar;
cb.Label.String = 'mm';
cb.FontSize = 10;

x = shiftdim(TPhy_v(cx,cy,:)); y = shiftdim(Dz_v(cx,cy,:));
sp2 =  subplot(3,2,2); hold off,
x2 = sort(x);
fy = Eval_PhaseRegression(coefz_v(cx,cy,:),x2);

plot(x2,fy,'Linewidth',1.5), hold on
plot(x,y,'*','MarkerSize',6)
xlabel(' Phase [rad]'), ylabel(' Z [mm]')
grid on



sp3 = subplot(3,2,3); imagesc(ex_v), caxis([0 0.15]), 
xlabel('u [Pixel]'); ylabel('v [Pixel]'); title('Z Vs X');
axis equal, xlim([0 1600]), ylim([0 1200])
cb =colorbar;
cb.Label.String = 'mm';
cb.FontSize = 10;


x = shiftdim(TPhy_v(cx,cy,:)); y = shiftdim(Dx_v(cx,cy,:));
sp4 = subplot(3,2,4); hold off,
x2 = sort(x);
fy = Eval_PhaseRegression(coefx_v(cx,cy,:),x2);


plot(x2,fy,'Linewidth',1.5), hold on
plot(x,y,'*','MarkerSize',6)
xlabel(' Z [mm]'), ylabel(' X [mm]')
grid on



sp5 = subplot(3,2,5); imagesc(ey_v), caxis([0 0.15]), 
xlabel('u [Pixel]'); ylabel('v [Pixel]'); title('Z Vs Y');
axis equal, xlim([0 1600]), ylim([0 1200])
cb =colorbar;
cb.Label.String = 'mm';
cb.FontSize = 10;

x = shiftdim(TPhy_v(cx,cy,:)); y = shiftdim(Dy_v(cx,cy,:));
sp6 = subplot(3,2,6); hold off,
x2 = sort(x);

fy = Eval_PhaseRegression(coefy_v(cx,cy,:),x2);

plot(x2,fy,'Linewidth',1.5), hold on
plot(x,y,'*','MarkerSize',6)
xlabel(' Z [mm]')
ylabel(' Y [mm]')
grid on


sp4.Position(3) = sp4.Position(3)*0.7; 
sp6.Position(3) = sp6.Position(3)*0.7; 
sp2.Position(3) = sp2.Position(3)*0.7; 


sp1.FontSize = 11; sp2.FontSize = 11;
sp3.FontSize = 11; sp4.FontSize = 11;
sp5.FontSize = 11; sp6.FontSize = 11;


%% Viartual planes extended to limits  

nVirtualplanes2 = 20;
Rv2 = repmat([1 0 0;0 1 0;0 0 1],[1,1,nVirtualplanes2]);
tv2 = repmat([0;0;0],[1 nVirtualplanes2]);
% tv(3,:) = [350, 800]; % Planes' distances from the camera
tv2(3,:) = linspace(400, 800, nVirtualplanes2); % Planes' distances from the camera

[Dx_v2,Dy_v2,Dz_v2,Up_v2,Vp_v2] = BackPropagation_Planes2(StereoParams,StereoType,Rv2,tv2,[m_imageHeight m_imageWidth],1);

TPhx_v2 = Up_v2*(2*pi)/FringePitch; % Virtual plane Phases
TPhy_v2 = Vp_v2*(2*pi)/FringePitch;

Z_v = Eval_PhaseRegression(coefz_v, TPhy_v2);
%%
aa = [275,275;
    1200,11;
    275, 1740;
    1175,1500
    750, 950];
a = aa(1,:);
linew = 1.3;
figure(5), hold off,
plot(shiftdim(Reg(a(1),a(2),:)), shiftdim(Z_v(a(1),a(2),:)),'-r','LineWidth',linew ) , hold on
plot(shiftdim(TPhy_v(a(1),a(2),:)), shiftdim(Dz_v(a(1),a(2),:)),'*r')
plot(shiftdim(TPhy_v2(a(1),a(2),:)), shiftdim(Dz_v2(a(1),a(2),:)),'-k')
title(['pixel (', num2str(a(1)),',', num2str(a(2)),')'])
legend('POL3','Data in Calib Volum','Stereo')
grid on

