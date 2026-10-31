
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
%         figExt.Children(i).Visible = 'off';
        
%         figExt.Children(i).FaceColor = 'r';
%         figExt.Children(i).EdgeColor = 'r';
    end
    rotate(figExt.Children(i), [0 1 0], -90)
end
hold on,

D0 = 399;
D1 = 500; D2 = 700;
D3 = 801;
ly = 150;
lx = 150;

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

figExt.View = [-32.5436   31.1308];

zlim([-150 150])
xlim([-150 150])
figExt.DataAspectRatio = [1 1.5 1];
figExt.XTickLabel = flipud(figExt.XTickLabel);
figExt.FontSize = 11;
exportgraphics(figure(2),'StereoCalib-Extrinsics_ENO.png','Resolution',800)


%% Create Virtual planes

nVirtualplanes = 30;
Rv = repmat([1 0 0;0 1 0;0 0 1],[1,1,nVirtualplanes]);
tv = repmat([0;0;0],[1 nVirtualplanes]);
% tv(3,:) = [350, 800]; % Planes' distances from the camera
tv(3,:) = linspace(420, 820, nVirtualplanes); % Planes' distances from the camera

[Dx_v,Dy_v,Dz_v,Up_v,Vp_v] = BackPropagation_Planes2(StereoParams,StereoType,Rv,tv,[m_imageHeight m_imageWidth],1);

TPhx_v = Up_v*(2*pi)/FringePitch; % Virtual plane Phases
TPhy_v = Vp_v*(2*pi)/FringePitch;



%%
exportgraphics(figure(2),'VirtualSampling-Extrinsics.png','Resolution',800)

%% R3D Targets and fitting to ideal plane

[erms,dist,Dx_ip, Dy_ip, Dz_ip, Dx_rp, Dy_rp, Dz_rp,errDis] = XYZ_R3D_Target(StereoParams,StereoType,Fxa,Fya,FringePitch,Indi>0,'Fy',Indi>0);

%% Regression Virtual 5th order
a = [97 1208];

% Using extrinsic positioning 

degreePol = [3 4 5 6]; 


[coefx_v,ex_v,~ ,meanErmsx]     = Polyfit3D(TPhy_v,Dx_v,a,degreePol); % Regresion de fase Vs X
[coefy_v,ey_v,~ ,meanErmsy]     = Polyfit3D(TPhy_v,Dy_v,a,degreePol); % Regresion de fase Vs Y
[coefz_v,ez_v,N3_v,meanErmsz]   = Polyfit3D(TPhy_v,Dz_v,a,degreePol); % Regresion de fase Vs Z

% [(2:6)' meanErmsx meanErmsy meanErmsz]
Lip_v = min(TPhy_v,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_v = max(TPhy_v,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión

%% Estimated experimental polynomial function with compensation -  3rd order


a = [27 41];

% Using extrinsic positioning 

degreePol = 3; 

[coefx_e,ex_e,N3_e]     = Polyfit3D(Fya.*Indi,Dx_ip.*Indi,a,degreePol); % Regresion de fase Vs X
[coefy_e,ey_e   ]       = Polyfit3D(Fya.*Indi,Dy_ip.*Indi,a,degreePol); % Regresion de fase Vs Y
[coefz_e,ez_e   ]       = Polyfit3D(Fya.*Indi,Dz_ip.*Indi,a,degreePol); % Regresion de fase Vs Z

Lip_e = min(Fya,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_e = max(Fya,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión

%% Estimated experimental polynomial function with compensation -  3rd order


a = [27 41];

% Using extrinsic positioning 

degreePol = 1; 

[coefx_ef,ex_ef,N3_e]     = Polyfit3D(Dz_ip.*Indi,Dx_ip.*Indi,a,0); % Regresion de fase Vs X

[coefy_ef,ey_ef   ]       = Polyfit3D(Dz_ip.*Indi,Dy_ip.*Indi,a,0); % Regresion de fase Vs Y

[coefz_ef,ez_ef   ]       = Racionalfit3D(Fya.*Indi,Dz_ip.*Indi,a,degreePol); % Regresion de fase Vs Z

Lip_e = min(Fya,[],3,'omitnan'); % Limite inferior de fase utilizado en la regresión
Lsp_e = max(Fya,[],3,'omitnan'); % Limite superior de fase utilizado en la regresión



%% Experimenta Vs Corrected pixelwise error functions 

% degreePol = 1;
% ndatos =30;
% Re  = repmat(reshape(linspace(0,1,ndatos),[1 1 ndatos]),size(Fya(:,:,1)));
% Reg = (max(Fya,[],3,'omitnan')-min(Fya,[],3,'omitnan')).*Re+ min(Fya,[],3,'omitnan');
% X_v = Eval_PhaseRegression(coefx_v, Reg); Y_v = Eval_PhaseRegression(coefy_v, Reg); Z_v = Eval_PhaseRegression(coefz_v, Reg);
% X_e = Eval_PhaseRegression(coefx_e, Reg); Y_e = Eval_PhaseRegression(coefy_e, Reg); Z_e = Eval_PhaseRegression(coefz_e, Reg);
% [coefx_t,ex_t,N3_t]     = Polyfit3D(X_v,X_e,a,degreePol); % Regresion de fase Vs X
% [coefy_t,ey_t   ]       = Polyfit3D(Y_v,Y_e,a,degreePol); % Regresion de fase Vs Y
% [coefz_t,ez_t   ]       = Polyfit3D(Z_v,Z_e,a,degreePol); % Regresion de fase Vs Z

a = [684 788];
degreePol = 1;
[coefx_t,ex_t,~,Ermsfcx]     = Polyfit3D(Dx_rp.*Indi,Dx_ip.*Indi,a,degreePol); % Regresion de fase Vs X
[coefy_t,ey_t,~,Ermsfcy]       = Polyfit3D(Dy_rp.*Indi,Dy_ip.*Indi,a,degreePol); % Regresion de fase Vs Y
[coefz_t,ez_t,~,Ermsfcz]       = Polyfit3D(Dz_rp.*Indi,Dz_ip.*Indi,a,degreePol); % Regresion de fase Vs Z

% return

for i = 1:numel(coefx_v)
    coefx_en{i} = coefx_t(:,:,1).*coefx_v{i};
    coefx_en{i}(:,:,end) = coefx_en{i}(:,:,end) +  coefx_t(:,:,2);

    coefy_en{i} = coefy_t(:,:,1).*coefy_v{i};
    coefy_en{i}(:,:,end) = coefy_en{i}(:,:,end) +  coefy_t(:,:,2);

    coefz_en{i} = coefz_t(:,:,1).*coefz_v{i};
    coefz_en{i}(:,:,end) = coefz_en{i}(:,:,end) +  coefz_t(:,:,2);
end
%% Guardar virtual

for i = 1:4

    coefx = coefx_v{i}; 
    coefy = coefy_v{i}; 
    coefz = coefz_v{i}; N3 = N3_e;
    % ex = ex_e; ey = ey_e; ez = ez_e;
    Lip = Lip_e; Lsp = Lsp_e;
    nomHybrid = '2';
    direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid',num2str(i+2),'_',nomHybrid,'_Vr.mat'];
    % save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
    save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

    disp(['Guardado ...'])

end

%% Guardar experimental

for i=1:4
    coefx = coefx_e{i};
    coefy = coefy_e{i};
    coefz = coefz_e{i}; N3 = N3_e;
    % ex = ex_e; ey = ey_e; ez = ez_e;
    Lip = Lip_e; Lsp = Lsp_e;
    nomHybrid = '2';
    direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid',num2str(i+2),'_',nomHybrid,'_Fa.mat'];
    % save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
    save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

    disp(['Guardado ...'])
end

%% Guardar virtual transformado

for i=1:4
    coefx = coefx_en{i};
    coefy = coefy_en{i}; 
    coefz = coefz_en{i}; N3 = N3_e;
    % ex = ex_e; ey = ey_e; ez = ez_e;
    Lip = Lip_e; Lsp = Lsp_e;
    nomHybrid = '2';
    direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid',num2str(i+2),'_',nomHybrid,'_Vrc.mat'];
    % save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
    save(direc,'coefx','coefy','coefz','N3','Lip','Lsp')

    disp(['Guardado ...'])
end

%% Guardando funcion de transformacion

coefx = coefx_t; coefy = coefy_t; coefz = coefz_t; 
% ex = ex_e; ey = ey_e; ez = ez_e; 

nomHybrid = 'TransfVir2Exp';
direc = ['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_hybrid1_',nomHybrid,'_Fa.mat'];
% save(direc,'coefx','coefy','coefz','ex','ey','ez','N3')
save(direc,'coefx','coefy','coefz')

disp(['Guardado ...'])

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


aa = [Vc(:), Uc(:)];
% 
% aa = [700, 700;
%       700, 1100];
a = aa(1,:);


            %3 4 5 6
hab_pols = [ 1 1 1 1; % Virtual
             0 0 0 0; % Experimental
             0 0 0 0];% Propuesto

ndatos = 100;
Re  = reshape(linspace(0,1,ndatos),[1 1 ndatos]);
Reg = (TPhy_v(a(1),a(2),end)-TPhy_v(a(1),a(2),1)).*Re+ TPhy_v(a(1),a(2),1);

Z_v = {};  Z_e = {}; Z_en = {};
for i = 1:4
    Z_v{i} = Eval_PhaseRegression(coefz_v{i}(a(1),a(2),:), Reg);
    Z_e{i} = Eval_PhaseRegression(coefz_e{i}(a(1),a(2),:), Reg);
    % Z_en = Eval_PhaseRegression(coefz_en(a(1),a(2),:)  , Reg);
    Z_en{i} = Eval_PhaseRegression(coefz_en{i}(a(1),a(2),:), Reg);
end

Z_vr = Z_v{4};

linew = 1.3;
gg = figure(900);hold off, 
gg.Position = [78, 108, 1239, 538];

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
    grafv{i} =  plot(shiftdim(Reg), shiftdim(Z_v {i}),'-.','Color',li(i,:),'LineWidth',linew,'DisplayName', ['VirPOL-',num2str(i+2)] ); hold on
    grafv{i}.Visible =  hab_pols(1,i);

    grafe{i} =  plot(shiftdim(Reg), shiftdim(Z_e {i}),'--','Color',li(i,:),'LineWidth',linew,'DisplayName', ['ExpPOL-',num2str(i+2)] );
    grafe{i}.Visible =  hab_pols(2,i);

    grafen{i}=  plot(shiftdim(Reg), shiftdim(Z_en{i}),'-' ,'Color',li(i,:),'LineWidth',linew,'DisplayName', ['cVirPOL-',num2str(i+2)] );
    grafen{i}.Visible = hab_pols(3,i);
end


grafip = plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_ip(a(1),a(2),:)),'ok','LineWidth',linew,'DisplayName', 'Corr-Data'  );
grafep = plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_rp(a(1),a(2),:)),'*m','LineWidth',linew,'DisplayName', 'Raw-Data'  );


grid on
grafe{1}.Parent(1).FontSize = 13;
xlabel('\phi [rad]')
ylabel('z [mm]')

tig = title([' \phi vs z - pixel (', num2str(a(1)),',', num2str(a(2)),')'],'FontSize',13);
legend('Location','southeastoutside')

ylim([375 800])
grafe{1}.Parent(1).Legend.Position = [0.4678    0.3060    0.1445    0.2082];


subplot(2,2,2), hold off, 
% figure(902),hold off,


for i =1:4
    grafv_{i} =  plot(shiftdim(Reg), shiftdim(Z_v {i}-Z_vr),'-.','Color',li(i,:),'LineWidth',linew,'DisplayName', ['VirPOL-',num2str(i+2)] ); hold on
    grafv_{i}.Visible =  hab_pols(1,i);

    grafe_{i} =  plot(shiftdim(Reg), shiftdim(Z_e {i}-Z_vr),'--','Color',li(i,:),'LineWidth',linew,'DisplayName', ['ExpPOL-',num2str(i+2)] );
    grafe_{i}.Visible =  hab_pols(2,i);

    grafen_{i}=  plot(shiftdim(Reg), shiftdim(Z_en{i}-Z_vr),'-' ,'Color',li(i,:),'LineWidth',linew,'DisplayName', ['cVirPOL-',num2str(i+2)] );
    grafen_{i}.Visible = hab_pols(3,i);
end

% grafep_ = plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(abs(Dz_ip(a(1),a(2),:)-Dz_rp(a(1),a(2),:))),'ok','LineWidth',linew );

grafip_ = plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_ip(a(1),a(2),:)),'ok','LineWidth',linew,'DisplayName', 'Corr-Data'  );
grafep_ = plot(shiftdim(Fya(a(1),a(2),:)), shiftdim(Dz_rp(a(1),a(2),:)),'*m','LineWidth',linew,'DisplayName', 'Raw-Data'  );


grafe_{1}.Parent(1).FontSize = 13;
grid on
ylim([-0.1 0.3])
xlim([70 380])
xlabel('Phase [rad]')
ylabel('[mm]')
title('Distance in Z regarding virtual data')

% Indixx = shiftdim(Ind(a(1),a(2),:));
% grafep = plot(shiftdim(Reg(a(1),a(2),Indixx)), shiftdim(Z_e(a(1),a(2),Indixx)),'ok','LineWidth',linew );

% figure(6), hold off, 
% grafd =  plot(shiftdim(Reg(a(1),a(2),:)), shiftdim(Z_e(a(1),a(2),:) - Z_v(a(1),a(2),:)),'-r','LineWidth',linew ); 

writerObj = VideoWriter('myVideo3','MPEG-4');
writerObj.FrameRate = 2;
open(writerObj);

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
            Z_v{i} = Eval_PhaseRegression(coefz_v{i}(a(1),a(2),:), Reg);
            Z_e{i} = Eval_PhaseRegression(coefz_e{i}(a(1),a(2),:), Reg);
            Z_en{i} = Eval_PhaseRegression(coefz_en{i}(a(1),a(2),:), Reg);

            grafv{i}.XData = shiftdim(Reg);  grafv{i}.YData = shiftdim(Z_v{i});
            grafe{i}.XData = shiftdim(Reg);  grafe{i}.YData = shiftdim(Z_e{i});
            grafen{i}.XData = shiftdim(Reg); grafen{i}.YData = shiftdim(Z_en{i});
        end

        Z_vr = Z_v{4};
        
        grafip.XData = shiftdim(Fya(a(1),a(2),:));  grafip.YData = shiftdim(Dz_ip(a(1),a(2),:));
        grafep.XData = shiftdim(Fya(a(1),a(2),:));  grafep.YData = shiftdim(Dz_rp(a(1),a(2),:));
        
        grafep.Parent(1).XLim = [0 150] + floor(min(Reg)/10)*10;
        grafep.Parent(1).XTick = (floor(min(Reg)/10)*10):30:(floor(min(Reg)/10)*10+150);
        tig.String = [' \phi vs z - Pixel (', num2str(a(1)),',', num2str(a(2)),')'];
        tig0.String = ['Analyzed Pixel - (', num2str(a(1)),',', num2str(a(2)),')'];




        for i = 1:4
            grafv_{i}.XData = shiftdim(Reg);  grafv_{i}.YData = shiftdim(Z_v{i}-Z_vr);
            grafe_{i}.XData = shiftdim(Reg);  grafe_{i}.YData = shiftdim(Z_e{i}-Z_vr);
            grafen_{i}.XData = shiftdim(Reg); grafen_{i}.YData = shiftdim(Z_en{i}-Z_vr);
        end



        %         Indixx = shiftdim(Ind(a(1),a(2),:));
        grafip_.XData = shiftdim(Fya(a(1),a(2),:));   grafip_.YData = shiftdim(abs(Dz_ip(a(1),a(2),:)-Dz_rp(a(1),a(2),:)));
        grafep_.XData = shiftdim(Fya(a(1),a(2),:));   grafep_.YData = shiftdim(abs(Dz_rp(a(1),a(2),:)-Dz_rp(a(1),a(2),:)));

        grafep_.Parent(1).XLim = [floor(min(grafep_.XData)/10)*10 ceil(max(grafep_.XData)/10)*10];
        grafep_.Parent(1).XTick = (floor(min(grafep_.XData)/10)*10):8:(ceil(max(grafep_.XData)/10)*10);




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


%     if(tim2>0.1 && kk<numel(Uc(:)))
%         kk = kk+1;
% %         a = aa(kk,:);
%         pp.Position = [aa(kk,2) aa(kk,1)];
%         tim1 = tic;
%     elseif(kk>=numel(Uc(:)))
%         op =0;
%     end


    if(tim2>20)
        op = 0;
    end

     
%     imi.Title.String = ['pixel (', num2str(a(1)),',', num2str(a(2)),') - time',num2str(tim2)];
    
end

close(writerObj);
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













