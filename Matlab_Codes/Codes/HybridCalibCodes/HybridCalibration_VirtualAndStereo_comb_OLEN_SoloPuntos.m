
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
% Fringe features: patterns period and shifts
FringePitch = 18;

%% Generacion de grafica de calibración estereo
% Esa seccion es solamente utilizada para generar el esquema estereo del
% sistema utilizando los parametros de calibración. 
%

gg = figure(2); hold off
gg.Position = [403   219   590   447];
figExt = showExtrinsics(StereoParams);
% figExt.Position = [0.1300    0.1100    0.7750    0.8150];
for i = 1:numel(figExt.Children)

        if(strcmp(figExt.Children(i).Type,'patch'))
            figExt.Children(i-1).Visible = 'off';
            figExt.Children(i).Visible = 'off';

            %         figExt.Children(i).FaceColor = 'r';
            %         figExt.Children(i).EdgeColor = 'r';
        end
%         figExt.Children(i).Type
        rotate(figExt.Children(i), [0 1 0], -90)
        if(strcmp(figExt.Children(i).Type,'patch') || strcmp(figExt.Children(i).Type,'line'))
           
   
%         1
%         aux = figExt.Children(i).XData;
        figExt.Children(i).XData = -figExt.Children(i).XData;
%         figExt.Children(i).YData = figExt.Children(i).ZData;
%         figExt.Children(i).YData = aux; 

        end

        if(strcmp(figExt.Children(i).Type,'text') )
            figExt.Children(i).Position(1) = -figExt.Children(i).Position(1);

            if(strcmp(figExt.Children(i).String,'1') || strcmp(figExt.Children(i).String,'2'))
                figExt.Children(i).Visible = 'off';
            end

        end


    end
hold on,

D0 = 350;
D1 = 500; D2 = 700;
D3 = 950;
ly = 200;
lx = -200;

[zcub,ycub] = meshgrid(linspace(D1,D2,2),linspace(-300,300,2));

gcub = surf(ycub,zcub,ycub*0+ly); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3;  gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
gcub = surf(ycub*0+lx,zcub,ycub); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
% return

[zcub,ycub] = meshgrid(linspace((D2+1),D3,2),linspace(-300,300,2));
gcub = surf(ycub,zcub,ycub*0+ly); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
gcub = surf(ycub*0+lx,zcub,ycub); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;


[zcub,ycub] = meshgrid(linspace(D0,(D1-1),2),linspace(-300,300,2));
gcub = surf(ycub,zcub,ycub*0+ly); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;
gcub = surf(ycub*0+lx,zcub,ycub); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;

limsz = 200;
%  [zcub,ycub] = meshgrid([520 920],[-300 300]);
%     gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3;  gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
%     gcub = surf(ycub*0-200,zcub,ycub); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
% % 
% % 
%     [zcub,ycub] = meshgrid([721 900],[-300 300]);
%     gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
%     gcub = surf(ycub*0-200,zcub,ycub); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
% % 
% % 
%     [zcub,ycub] = meshgrid([350 519],[-300 300]);
%     gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;
%     gcub = surf(ycub*0-200,zcub,ycub); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;

    

xlabel('Y [mm]'), ylabel('Z [mm]'), zlabel('X [mm]')

figExt.Title.Visible = 'off';
figExt.XLabel.Visible = 'off';
figExt.YLabel.Visible = 'off';
figExt.ZLabel.Visible = 'off';

figExt.View = [-32.5436   31.1308];

  xlim([-200 200])
    zlim([-200 limsz])
    ylim([-100 1000])

 figExt.ZDir = 'reverse';
    figExt.XDir = 'reverse';
    figExt.FontSize = 13;
   figExt.XAxis.LineWidth = 1.5;
    figExt.YAxis.LineWidth = 1.5;
    figExt.ZAxis.LineWidth = 1.5;
    figExt.LineWidth = 1.5;
    figExt.View = [-31.2078   30.2301];

    figExt.DataAspectRatio = [1 1 1];


% zlim([-150 150])
% xlim([-150 150])
% figExt.DataAspectRatio = [1 a 1];
% figExt.XTickLabel = flipud(figExt.XTickLabel);
% figExt.FontSize = 11;
% exportgraphics(figure(900),'StereoCalib-Extrinsics.png','Resolution',800)


%% Create Virtual planes

nVirtualplanes = 30;
Rv = repmat([1 0 0;0 1 0;0 0 1],[1,1,nVirtualplanes]);
tv = repmat([0;0;0],[1 nVirtualplanes]);
% tv(3,:) = [350, 800]; % Planes' distances from the camera
tv(3,:) = linspace(350, 950, nVirtualplanes); % Planes' distances from the camera

[Dx_v,Dy_v,Dz_v,Up_v,Vp_v] = BackPropagation_Planes2(StereoParams,StereoType,Rv,tv,[m_imageHeight m_imageWidth],1);

TPhx_v = Up_v*(2*pi)/FringePitch; % Virtual plane Phases
TPhy_v = Vp_v*(2*pi)/FringePitch;

%%
exportgraphics(figure(2),'VirtualSampling-Extrinsics.png','Resolution',800)

%% R3D Targets and fitting to ideal plane

[erms,dist,Dx_ip, Dy_ip, Dz_ip, Dx_rp, Dy_rp, Dz_rp,errDis] = XYZ_R3D_Target(StereoParams,StereoType,Fxa,Fya,FringePitch,Indi>0,'Fy',Indi>0);

%%

a = [960 1280];
degreePol = 1;
[coefx_t,ex_t,~,Ermsfcx]     = Polyfit3D(Dx_rp.*Indi,Dx_ip.*Indi,a,degreePol); % Regresion de fase Vs X
[coefy_t,ey_t,~,Ermsfcy]     = Polyfit3D(Dy_rp.*Indi,Dy_ip.*Indi,a,degreePol); % Regresion de fase Vs Y
[coefz_t,ez_t,~,Ermsfcz]     = Polyfit3D(Dz_rp.*Indi,Dz_ip.*Indi,a,degreePol); % Regresion de fase Vs Z

Dx_vc = Dx_v.*coefx_t(:,:,1)+coefx_t(:,:,2);
Dy_vc = Dy_v.*coefy_t(:,:,1)+coefy_t(:,:,2);
Dz_vc = Dz_v.*coefz_t(:,:,1)+coefz_t(:,:,2);


return
%% Grafica error de ajuste 

lie = -1;
lse = 1;

figExt0 = figure(500) 
ims = 12;
imagesc(errDis(:,:,ims))
colorbar
caxis([-1 1])
figExt0.Children(2).FontSize = 16;


figExt = figure(501); hold off
Zsnorm = errDis(:,:,ims);
Zsnorm = uint8(round(254* (Zsnorm-lie)/(lse-lie)))+1;
Zsnorm(isnan(Zsnorm)) = 1;
colors = (parula(255));
ColR = double(Zsnorm*0); ColG = ColR; ColB = ColR;

ColR(:) = colors(Zsnorm,1);
ColG(:) = colors(Zsnorm,2);
ColB(:) = colors(Zsnorm,3);
Col = cat(3,ColR,ColG,ColB);

mesh(Dx_rp(:,:,ims),Dy_rp(:,:,ims),errDis(:,:,ims),Col)
zlim([-1.5 1.5])

hold on 
aa = 100;
g = surf(Dx_ip(1:aa:end,1:aa:end,ims)*1.2,Dy_ip(1:aa:end,1:aa:end,ims)*1.2,0*errDis(1:aa:end,1:aa:end,ims));
figExt.Children(2).DataAspectRatio = [1 1 0.04]
figExt.Children(2).View = [-28.8000   33.9050];
figExt.Children(2).FontSize = 14;
xlim([1.08*min(Dx_rp(:,:,ims),[],[1 2]) 1.05*max(Dx_rp(:,:,ims),[],[1 2]) ])
g.FaceColor = 'r'; g.FaceAlpha = 0.2;
g.EdgeColor = 'k'; g.EdgeAlpha = 0.5;

saveas(figure(500),'errmap-Stereo-Pose12.svg','svg')
saveas(figure(501),'errmap-Stereo-Pose12-R3D.svg','svg')

exportgraphics(figure(501),sprintf('errmap-Stereo-Pose12-R3D %d.png',ims),'resolution',500)
exportgraphics(figure(500),sprintf('errmap-Stereo-Pose12 %d.png',ims),'resolution',500)

%% Graficas Relacion lineal (Funcion de correccion) x-x' y-y' z-z'

a = [960 1280];


gg = figure(90), 
hold off

Z_en = Eval_PhaseRegression(coefx_t(a(1),a(2),:), Dx_rp(a(1),a(2),:));
plot(shiftdim(Dx_rp(a(1),a(2),:)), shiftdim(Z_en),'LineWidth',2);
hold on,
plot(shiftdim(Dx_rp(a(1),a(2),:)), shiftdim(Dx_ip(a(1),a(2),:)),'*');
grid on
gg.Children(1).FontSize  = 18;
% xlabel(['$x_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
% ylabel(['$x''_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
xlabel(['$x$'],'interpreter','latex','FontSize',20)
ylabel(['$x''$'],'interpreter','latex','FontSize',20)
axis equal
ylim([min(shiftdim(Dx_rp(a(1),a(2),:)))*0.99 1.01*max(shiftdim(Dx_rp(a(1),a(2),:)))])
xlim(ylim)
legend(['x'' =',num2str(round(coefx_t(a(1),a(2),1),5)),'x' ...
    num2str(round(coefx_t(a(1),a(2),2),3))], 'Data', ...
    'Data','Interpreter','latex','Location','southeast');


gg1 =figure(91), 
hold off
Z_en = Eval_PhaseRegression(coefy_t(a(1),a(2),:), Dy_rp(a(1),a(2),:));
plot(shiftdim(Dy_rp(a(1),a(2),:)), shiftdim(Z_en),'LineWidth',2);
hold on, 
plot(shiftdim(Dy_rp(a(1),a(2),:)), shiftdim(Dy_ip(a(1),a(2),:)),'*');

grid on
gg1.Children(1).FontSize  = 18;
% xlabel(['$y_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
% ylabel(['$y''_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
xlabel(['$y$'],'interpreter','latex','FontSize',20)
ylabel(['$y''$'],'interpreter','latex','FontSize',20)
axis equal
ylim([min(shiftdim(Dy_rp(a(1),a(2),:)))*0.99 1.01*max(shiftdim(Dy_rp(a(1),a(2),:)))])
xlim(ylim)

legend(['y'' =',num2str(round(coefy_t(a(1),a(2),1),5)),'y' ...
    num2str(round(coefy_t(a(1),a(2),2),3))], 'Data',...
    'Data','Interpreter','latex','Location','southeast');


gg2 = figure(92), 
hold off
Z_en = Eval_PhaseRegression(coefz_t(a(1),a(2),:), Dz_rp(a(1),a(2),:));
plot(shiftdim(Dz_rp(a(1),a(2),:)), shiftdim(Z_en),'LineWidth',2);
hold on, 
plot(shiftdim(Dz_rp(a(1),a(2),:)), shiftdim(Dz_ip(a(1),a(2),:)),'*');
grid on
gg2.Children(1).FontSize  = 18;
% xlabel(['$z_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
% ylabel(['$z''_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
xlabel(['$z$'],'interpreter','latex','FontSize',20)
ylabel(['$z''$'],'interpreter','latex','FontSize',20)
axis equal
ylim([min(shiftdim(Dz_rp(a(1),a(2),:)))*0.99 1.01*max(shiftdim(Dz_rp(a(1),a(2),:)))])
xlim(ylim)

legend(['z'' =',num2str(round(coefz_t(a(1),a(2),1),5)),'z' ...
    num2str(round(coefz_t(a(1),a(2),2),3))], 'Data',...
    'Data','Interpreter','latex','Location','southeast');

% legend('x-x''',['x'' = ',num2str()])
saveas(figure(90),'x''x.svg','svg')
saveas(figure(91),'y''y.svg','svg')
saveas(figure(92),'z''z.svg','svg')
%% Graficas coordenadas Reconstruidas y corregidas vs fase (Figura Articulo)


gg = figure(95), 
hold off

ms = 7;
mti = 'o';
plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dx_rp(a(1),a(2),:)),'*','MarkerSize',6), hold on
plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dx_ip(a(1),a(2),:)),mti,'MarkerSize',ms)
grid on

gg.Children(1).FontSize  = 18;
% xlabel(['$x_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
% ylabel(['$x''_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
xlabel(['$\phi$ [rad]'],'interpreter','latex','FontSize',20)
ylabel(['$x$[mm]'],'interpreter','latex','FontSize',20)
xlim([min(shiftdim(Fya(a(1),a(2),:)))*0.90 1.05*max(shiftdim(Fya(a(1),a(2),:)))])
% xlim(ylim)
legend('$\hat{x}$', '$\hat{x}''$', ...
    'Data','Interpreter','latex','Location','southeast');
gg.Children(1).FontSize  = 20;
saveas(figure(95),'phi-x-x''-zoom.svg','svg')


gg = figure(96), 
hold off

plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dy_rp(a(1),a(2),:)),'*','MarkerSize',ms), hold on
plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dy_ip(a(1),a(2),:)),mti,'MarkerSize',ms)
grid on

gg.Children(1).FontSize  = 18;
% xlabel(['$x_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
% ylabel(['$x''_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
xlabel(['$\phi$ [rad]'],'interpreter','latex','FontSize',20)
ylabel(['$y$[mm]'],'interpreter','latex','FontSize',20)
xlim([min(shiftdim(Fya(a(1),a(2),:)))*0.90 1.05*max(shiftdim(Fya(a(1),a(2),:)))])
% xlim(ylim)
legend('$\hat{y}$', '$\hat{y}''$', ...
    'Data','Interpreter','latex','Location','southeast');


gg.Children(1).FontSize  = 20;


saveas(figure(96),'phi-y-y''-zoom.svg','svg')

gg = figure(97), 
hold off

plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_rp(a(1),a(2),:)),'*','MarkerSize',ms), hold on
plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_ip(a(1),a(2),:)),mti,'MarkerSize',ms)
grid on

gg.Children(1).FontSize  = 18;
% xlabel(['$x_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
% ylabel(['$x''_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
xlabel(['$\phi$ [rad]'],'interpreter','latex','FontSize',20)
ylabel(['$z$[mm]'],'interpreter','latex','FontSize',20)
xlim([min(shiftdim(Fya(a(1),a(2),:)))*0.90 1.05*max(shiftdim(Fya(a(1),a(2),:)))])
% xlim(ylim)
legend('$\hat{z}$', '$\hat{z}''$', ...
    'Data','Interpreter','latex','Location','southeast');


gg.Children(1).FontSize  = 20;

saveas(figure(97),'phi-z-z''-zoom.svg','svg')

% saveas(figure(94),'VirtualDataAndCorrectedZoom.svg','svg')





%%

gg = figure(94), 
hold off

plot(shiftdim(TPhy_v(a(1),a(2),:)), shiftdim(Dz_v(a(1),a(2),:)),'*-','LineWidth',1);
hold on,
plot(shiftdim(TPhy_v(a(1),a(2),:)), shiftdim(Dz_vc(a(1),a(2),:)),'o--','LineWidth',1);


% plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_ip(a(1),a(2),:)),'*');
% plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_rp(a(1),a(2),:)),'+');
grid on

gg.Children(1).FontSize  = 14;
% xlabel(['$x_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
% ylabel(['$x''_{(',num2str(a(1)),',',num2str(a(2)),')}$'],'interpreter','latex','FontSize',16)
xlabel(['$\phi$ [rad]'],'interpreter','latex','FontSize',20)
ylabel(['$z$[mm]'],'interpreter','latex','FontSize',20)
xlim([min(shiftdim(TPhy_v(a(1),a(2),:)))*0.90 1.05*max(shiftdim(TPhy_v(a(1),a(2),:)))])
% xlim(ylim)
legend('$\hat{z}$', '$\hat{z}''$', ...
    'Data','Interpreter','latex','Location','southeast');


gg.Children(1).FontSize  = 18;


saveas(figure(94),'VirtualDataAndCorrectedZoom.svg','svg')




%% Ajustes de puntos virtuales corregidos Xc,Yc,Zc como pol de fase 
a = [27 41];

% Using extrinsic positioning 

degreePol = [3 4 5 6]; 

[coefx_f,ex_f,N3_f,meanErmsx]       = Polyfit3D(TPhy_v,Dx_vc,a,degreePol); % Regresion de fase Vs X
[coefy_f,ey_f,F0,meanErmsy   ]      = Polyfit3D(TPhy_v,Dy_vc,a,degreePol); % Regresion de fase Vs Y
[coefz_f,ez_f,F0,meanErmsz  ]       = Polyfit3D(TPhy_v,Dz_vc,a,degreePol); % Regresion de fase Vs Z

Lip_e = min(TPhy_v,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_e = max(TPhy_v,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión
%% Ajustes de puntos virtuales corregidos Xc,Yc,Zc como pol de fase 

a = [27 41];

% Using extrinsic positioning 

degreePol = [3 4 5 6]; 

[coefx_f,ex_f,N3_f,meanErmsx]       = Polyfit3D(TPhy_v,Dx_vc,a,degreePol); % Regresion de fase Vs X
[coefy_f,ey_f,F0,meanErmsy   ]      = Polyfit3D(TPhy_v,Dy_vc,a,degreePol); % Regresion de fase Vs Y
[coefz_f,ez_f,F0,meanErmsz  ]       = Polyfit3D(TPhy_v,Dz_vc,a,degreePol); % Regresion de fase Vs Z

Lip_e = min(TPhy_v,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_e = max(TPhy_v,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión
%% Estimated experimental polynomial function with compensation -  3rd order


a = [27 41];

% Using extrinsic positioning 

degreePol = 3; 

[coefx_e,ex_e,N3_e,meanErmsx ]     = Polyfit3D(Fya.*Indi,Dx_ip.*Indi,a,degreePol); % Regresion de fase Vs X

h = gca;
h.FontSize = 13;
h.Children(2).MarkerSize = 10;
h.Children(1).LineWidth = 2;
xlabel(' Phase [rad]')
ylabel(' X [mm]')
grid on
saveas(h,'POL3 - X Vs Phi','svg')

[coefy_e,ey_e,~,meanErmsy   ]       = Polyfit3D(Fya.*Indi,Dy_ip.*Indi,a,degreePol); % Regresion de fase Vs Y

h = gca;
h.FontSize = 13;
h.Children(2).MarkerSize = 10;
h.Children(1).LineWidth = 2;
xlabel(' Phase [rad]')
ylabel(' Y [mm]')
grid on
saveas(h,'POL3 - Y Vs Phi','svg')


[coefz_e,ez_e,~,meanErmsz   ]       = Polyfit3D(Fya.*Indi,Dz_ip.*Indi,a,degreePol); % Regresion de fase Vs Z

h = gca;
h.FontSize = 13;
h.Children(2).MarkerSize = 10;
h.Children(1).LineWidth = 2;
xlabel(' Phase [rad]')
ylabel(' Z [mm]')
grid on
saveas(h,'POL3 - Z Vs Phi','svg')


Lip_e = min(Fya,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_e = max(Fya,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión



%% Estimated experimental polynomial function with compensation -  3rd order


a = [27 41];

% Using extrinsic positioning 

degreePol = 1; 

[coefx_ef,ex_ef,N3_e,meanErmsxf ]     = Polyfit3D(Dz_ip.*Indi,Dx_ip.*Indi,a,0); % Regresion de fase Vs X

h = gca;
h.FontSize = 13;
h.Children(2).MarkerSize = 10;
h.Children(1).LineWidth = 2;
xlabel(' Z [mm]')
ylabel(' X [mm]')
grid on
saveas(h,'POL1 - X Vs Z','svg')

[coefy_ef,ey_ef,~,meanErmsyf   ]       = Polyfit3D(Dz_ip.*Indi,Dy_ip.*Indi,a,0); % Regresion de fase Vs Y

h = gca;
h.FontSize = 13;
h.Children(2).MarkerSize = 10;
h.Children(1).LineWidth = 2;
xlabel(' Z [mm]')
ylabel(' Y [mm]')
grid on
saveas(h,'POL1 - Y Vs Z','svg')


[coefz_ef,ez_ef   ]       = Racionalfit3D(Fya.*Indi,Dz_ip.*Indi,a,degreePol); % Regresion de fase Vs Z
h = gca;
h.FontSize = 13;
h.Children(2).MarkerSize = 10;
h.Children(1).LineWidth = 2;
xlabel(' Phase [rad]')
ylabel(' Z [mm]')
grid on
saveas(h,'Frac - Z Vs Phi','svg')

Lip_e = min(Fya,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_e = max(Fya,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión


%% Ajustes de puntos virtuales corregidos Zc como pol de fase y  Xc,Yc proporcional a Z
a = [27 41];

% Using extrinsic positioning 

degreePol = 0; 

[coefx_z,ex_z,N3_z]    = Polyfit3D(Dz_vc,Dx_vc,a,degreePol); % Regresion de fase Vs X
[coefy_z,ey_z   ]      = Polyfit3D(Dz_vc,Dy_vc,a,degreePol); % Regresion de fase Vs Y


Lip_e = min(TPhy_v,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_e = max(TPhy_v,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión


%% Guardar (X,Y,Z) como POLs de Fase

for i = 1:4

    coefx = coefx_f{i}; 
    coefy = coefy_f{i}; 
    coefz = coefz_f{i}; N3 = N3_f;
    % ex = ex_e; ey = ey_e; ez = ez_e;
    Lip = Lip_e; Lsp = Lsp_e;
    nomHybrid = '7';
    direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid',num2str(i+2),'_',nomHybrid,'_Vr.mat'];
    % save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
    save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

    disp(['Guardado ...'])

end

%% Guardar Z como POL de Fase y (X,Y) proporcional a Z

for i = 1:4

    coefx = coefx_z; 
    coefy = coefy_z; 
    coefz = coefz_f{i}; N3 = N3_f;
    % ex = ex_e; ey = ey_e; ez = ez_e;
    Lip = Lip_e; Lsp = Lsp_e;
    nomHybrid = '6';
    direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid',num2str(i+2),'_',nomHybrid,'_Vr.mat'];
    % save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
    save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

    disp(['Guardado ...'])

end

%% Solo visualizacion
ndatos = 30;
Re  = repmat(reshape(linspace(0,1,ndatos),[1 1 ndatos]),size(TPhy_v(:,:,1)));
Reg = (TPhy_v(:,:,end)-TPhy_v(:,:,1)).*Re+ TPhy_v(:,:,1);


Z_v = Eval_PhaseRegression(coefz_v{5}, Reg);
Z_e3 = Eval_PhaseRegression(coefz_e{1}, Reg);
Z_e4 = Eval_PhaseRegression(coefz_e{2}, Reg);
Z_e5 = Eval_PhaseRegression(coefz_e{3}, Reg);
Z_e = Eval_PhaseRegression(coefz_e{2}, Reg);
Z_en = Eval_PhaseRegression(coefz_en, Reg);


%%

op = 1;

[Vc,Uc] = meshgrid(100:200:1100,100:200:1500);


% aa = [Vc(:), Uc(:)];
% 
% aa = [700, 700;
%       700, 1100];
a = [960 1280];


            %3 4 5 6
% hab_pols = [ 0 0 0 0; % Propuesto
%              1 1 1 1];% Experimental

hab_pols = [ 1 1 1 1; % Propuesto
             0 0 0 0];% Experimental

ndatos = 100;
Re  = reshape(linspace(0,1,ndatos),[1 1 ndatos]);
Reg = (TPhy_v(a(1),a(2),end)-TPhy_v(a(1),a(2),1)).*Re+ TPhy_v(a(1),a(2),1);

Z_v = {};  Z_e = {}; %Z_en = {};
for i = 1:4
    Z_v{i} = Eval_PhaseRegression(coefz_f{i}(a(1),a(2),:), Reg);
    Z_e{i} = Eval_PhaseRegression(coefz_e{i}(a(1),a(2),:), Reg);
    % Z_en = Eval_PhaseRegression(coefz_en(a(1),a(2),:)  , Reg);
%     Z_en{i} = Eval_PhaseRegression(coefz_en{i}(a(1),a(2),:), Reg);
end

Z_vr = Z_v{4};

linew = 1.3;
gg = figure(900);hold off, 
gg.Position = [216        1014        1239         399];

imi = subplot(2,2,4);
imagesc(0*ez_e{1})
hold on, 
pp = drawpoint("Position",[600 600]);
pp.Color = [0.8 0.7 0];
caxis([0 0.2])
axis equal
ylim([0 1200])
xlim([0 1600])
tig0 = title(['Analyzed Pixel - (', num2str(a(1)),',', num2str(a(2)),')']);
hold on, 
plot(Uc(:),Vc(:),'or')


subplot(2,2,[1 3]), hold off, 
% figure(901), hold off,

li = lines(4);

for i =1:4
    grafv{i} =  plot(shiftdim(Reg), shiftdim(Z_v {i}),'-','Color',li(i,:),'LineWidth',linew,'DisplayName', ['VirPOL-',num2str(i+2)] ); hold on
    grafv{i}.Visible =  hab_pols(1,i);

    grafe{i} =  plot(shiftdim(Reg), shiftdim(Z_e {i}),'--','Color',li(i,:),'LineWidth',linew,'DisplayName', ['ExpPOL-',num2str(i+2)] );
    grafe{i}.Visible =  hab_pols(2,i);

%     grafen{i}=  plot(shiftdim(Reg), shiftdim(Z_en{i}),'-' ,'Color',li(i,:),'LineWidth',linew,'DisplayName', ['cVirPOL-',num2str(i+2)] );
%     grafen{i}.Visible = hab_pols(3,i);
end


grafip  = plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_ip(a(1),a(2),:)),'+b','LineWidth',linew,'DisplayName', 'Corr-Data'  );
grafvp = plot(shiftdim(TPhy_v(a(1),a(2),:)), shiftdim(Dz_vc(a(1),a(2),:)),'or','LineWidth',linew,'DisplayName', 'Vir-Points'  );
% grafep = plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_rp(a(1),a(2),:)),'*m','LineWidth',linew,'DisplayName', 'Raw-Data'  );


grid on
grafe{1}.Parent(1).FontSize = 13;
xlabel('\phi [rad]')
ylabel('z [mm]')

tig = title([' \phi vs z - pixel (', num2str(a(1)),',', num2str(a(2)),')'],'FontSize',13);
legend('Location','southeastoutside')

ylim([300 1000])
grafe{1}.Parent(1).Legend.Position = [0.4678    0.3060    0.1445    0.2082];

% saveas(figure(900),'RegexpPolys.svg','svg')

% xlim([148 160]),  ylim([595 625])
% saveas(figure(900),'RegexpPolysZoomInside.svg','svg')

% xlim([38 58]), ylim([340 375])
% saveas(figure(900),'RegProposedPolysZoomFront.svg','svg')



xlim([38 100]), ylim([250 500])
% saveas(figure(900),'RegexpPolysZoomFront.svg','svg')
saveas(figure(900),'RegProposedPolysZoomFront.svg','svg')

xlim([190 215]), ylim([790 960])
% saveas(figure(900),'RegexpPolysZoomBack.svg','svg')

% xlim([209 213]), ylim([925 952])
saveas(figure(900),'RegProposedPolysZoomBack.svg','svg')

return
% subplot(2,2,2), hold off, 
% figure(902),hold off,


% for i =1:4
%     grafv_{i} =  plot(shiftdim(Reg), shiftdim(Z_v {i}-Z_vr),'-','Color',li(i,:),'LineWidth',linew,'DisplayName', ['VirPOL-',num2str(i+2)] ); hold on
%     grafv_{i}.Visible =  hab_pols(1,i);

%     grafe_{i} =  plot(shiftdim(Reg), shiftdim(Z_e {i}-Z_vr),'--','Color',li(i,:),'LineWidth',linew,'DisplayName', ['ExpPOL-',num2str(i+2)] );
%     grafe_{i}.Visible =  hab_pols(2,i);

%     grafen_{i}=  plot(shiftdim(Reg), shiftdim(Z_en{i}-Z_vr),'-' ,'Color',li(i,:),'LineWidth',linew,'DisplayName', ['cVirPOL-',num2str(i+2)] );
%     grafen_{i}.Visible = hab_pols(3,i);
% end

% grafep_ = plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(abs(Dz_ip(a(1),a(2),:)-Dz_rp(a(1),a(2),:))),'ok','LineWidth',linew );

% grafip_ = plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_ip(a(1),a(2),:)),'+b','LineWidth',linew,'DisplayName', 'Corr-Data'  );
% grafvp_ =  plot(shiftdim(TPhy_v(a(1),a(2),:)), shiftdim(Dz_vc(a(1),a(2),:)),'or','LineWidth',linew,'DisplayName', 'Vir-Points'  );

% grafep_ = plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_rp(a(1),a(2),:)),'*m','LineWidth',linew,'DisplayName', 'Raw-Data'  );


% grafe_{1}.Parent(1).FontSize = 13;
% grid on
% ylim([-0.1 0.3])
% xlim([70 380])
% xlabel('Phase [rad]')
% ylabel('[mm]')
% title('Distance in Z regarding virtual data')

% Indixx = shiftdim(Ind(a(1),a(2),:));
% grafep = plot(shiftdim(Reg(a(1),a(2),Indixx)), shiftdim(Z_e(a(1),a(2),Indixx)),'ok','LineWidth',linew );

% figure(6), hold off, 
% grafd =  plot(shiftdim(Reg(a(1),a(2),:)), shiftdim(Z_e(a(1),a(2),:) - Z_v(a(1),a(2),:)),'-r','LineWidth',linew ); 

% writerObj = VideoWriter('Prueba','MPEG-4');
% writerObj.FrameRate = 2;
% open(writerObj);

kk = 0;
tim1 = tic;
pp_NP = pp.Position;
while(op)
    
    tim2 = toc(tim1);

    if(sum(pp.Position~= pp_NP)>0)


        a = [round(pp.Position(2)), round(pp.Position(1))];
        Re  = reshape(linspace(0,1,ndatos),[1 1 ndatos]);
        Reg = (TPhy_v(a(1),a(2),end)-TPhy_v(a(1),a(2),1)).*Re+ TPhy_v(a(1),a(2),1);


        for i = 1:4
            Z_v{i} = Eval_PhaseRegression(coefz_f{i}(a(1),a(2),:), Reg);
            Z_e{i} = Eval_PhaseRegression(coefz_e{i}(a(1),a(2),:), Reg);
%             Z_en{i} = Eval_PhaseRegression(coefz_en{i}(a(1),a(2),:), Reg);

            grafv{i}.XData = shiftdim(Reg);  grafv{i}.YData = shiftdim(Z_v{i});
            grafe{i}.XData = shiftdim(Reg);  grafe{i}.YData = shiftdim(Z_e{i});
%             grafen{i}.XData = shiftdim(Reg); grafen{i}.YData = shiftdim(Z_en{i});
        end

        Z_vr = Z_v{4};
        
        grafip.XData = shiftdim(Fya(a(1),a(2),:));  grafip.YData = shiftdim(Dz_ip(a(1),a(2),:));
        grafvp.XData = shiftdim(TPhy_v(a(1),a(2),:));  grafvp.YData = shiftdim(Dz_vc(a(1),a(2),:));
        
%         grafvp.Parent(1).XLim = [0 150] + floor(min(Reg)/10)*10;
%         grafvp.Parent(1).XTick = (floor(min(Reg)/10)*10):30:(floor(min(Reg)/10)*10+150);

        tig.String = [' \phi vs z - Pixel (', num2str(a(1)),',', num2str(a(2)),')'];
        tig0.String = ['Analyzed Pixel - (', num2str(a(1)),',', num2str(a(2)),')'];




%         for i = 1:4
%             grafv_{i}.XData = shiftdim(Reg);  grafv_{i}.YData = shiftdim(Z_v{i}-Z_vr);
%             grafe_{i}.XData = shiftdim(Reg);  grafe_{i}.YData = shiftdim(Z_e{i}-Z_vr);
%             grafen_{i}.XData = shiftdim(Reg); grafen_{i}.YData = shiftdim(Z_en{i}-Z_vr);
%         end



        %         Indixx = shiftdim(Ind(a(1),a(2),:));
%         grafip_.XData = shiftdim(Fya(a(1),a(2),:));   grafip_.YData = shiftdim(abs(Dz_ip(a(1),a(2),:)-Dz_rp(a(1),a(2),:)));
%         grafep_.XData = shiftdim(Fya(a(1),a(2),:));   grafep_.YData = shiftdim(abs(Dz_rp(a(1),a(2),:)-Dz_rp(a(1),a(2),:)));
%         grafvp_.XData = shiftdim(TPhy_v(a(1),a(2),:));   grafvp_.YData = shiftdim(abs(Dz_vc(a(1),a(2),:)-Dz_v(a(1),a(2),:)));

%         grafvp_.Parent(1).XLim = [floor(min(grafvp_.XData)/10)*10 ceil(max(grafvp_.XData)/10)*10];
%         grafvp_.Parent(1).XTick = (floor(min(grafvp_.XData)/10)*10):8:(ceil(max(grafvp_.XData)/10)*10);




        pp_NP = pp.Position;
        tim1 = tic;
        drawnow
%         pause()
%         exportgraphics(figure(901),['I',num2str(kk),'.pdf'],'ContentType','vector')
%         exportgraphics(figure(902),['I',num2str(kk),'_2.pdf'],'ContentType','vector')
%         exportgraphics(figure(900),['I',num2str(kk),'.png'],'Resolution',500)
%         frame = imread(['I',num2str(kk),'_m.png']);
        
%         frame2 = uint8(255*ones([2900 5600 3]));
%         frame2((1:size(frame,1))+150,(1:size(frame,2))+150,:) = frame;

%         imwrite(frame2,['I',num2str(kk),'_m.png'])

%         if (size(frame,[1 2 ])~=[writerObj.Height writerObj.Width])
%             
%         end
%         frame = imresize(frame, [writerObj.Height writerObj.Width 3]);
%         F = getframe(figure(900)) ;
%         writeVideo(writerObj, frame);
    end

    pause(0.1)


    if(tim2>0.1 && kk<numel(Uc(:)))
        kk = kk+1;
%         a = aa(kk,:);
        pp.Position = [aa(kk,2) aa(kk,1)];
        tim1 = tic;
    elseif(kk>=numel(Uc(:)))
        op =0;
    end


    if(tim2>20)
        op = 0;
    end

     
%     imi.Title.String = ['pixel (', num2str(a(1)),',', num2str(a(2)),') - time',num2str(tim2)];
    
end

% close(writerObj);
%% Guardar video
  % create the video writer with 1 fps
 
  % set the seconds per image
% open the video writer

% write the frames to the video
for i=1:length(F)
    % convert the image to a frame
    frame = F(i) ;    
    
end
% close the writer object


%%













