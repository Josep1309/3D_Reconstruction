

pathExp   = '23-03-07 - Pruebas';
pathR3D = 'Sphere3';

load(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_PhasesData.mat'],'Fx','Fy','MaskC','images')
% MaskC = Mask;

MaskC([1:15 end-15:end],:,:) = 0;
MaskC(:,[1:15 end-15:end],:) = 0;
Indi = NaN*MaskC; Indi(MaskC>0) = 1;

%%
% Camera and projector resolutions
m_imageWidth = 1600;        %1936   %1280 ;     %2048
m_imageHeight = 1200;       %1464   %1024 ;     %1536
m_projectorWidth =  912;    %912    %1280;      %912
m_projectorHeight = 1140;   %1140   %800;       %1140


pathExp   = '23-03-07 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Estereo_TSC_0_2';

StereoType = 'MT';

if(strcmp(StereoType,'BT'))
    StereoParams = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'.mat']);
    typeCalib = 1;
else
    load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'.mat']);
    typeCalib = 3;

end


Fd = 'Fy';
res = [m_projectorHeight m_projectorWidth];


[Xs,Ys,Zs] = StereoReconstruction(Fx,Fy,MaskC,18,StereoParams,typeCalib,Fd);

%% R3D Hybrid model 2

pathExp   = '23-03-07 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Estereo_TSC_0_2';
HybridModelname = 'hybrid3_2_Fa';
HybridModel1 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
[Xh3,Yh3,Zh3] = HybridReconstruction(Fy.*Indi,1,HybridModel1);
%% R3D Hybrid model 2

pathExp   = '23-03-07 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Estereo_TSC_0_2';
HybridModelname = 'hybrid6_2_Fa';
HybridModel2 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
[Xh6,Yh6,Zh6] = HybridReconstruction(Fy.*Indi,1,HybridModel2);
%% R3D Hybrid model 2

pathExp   = '23-03-07 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Estereo_TSC_0_2';
HybridModelname = 'hybrid6_v_Fa';
HybridModel3 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
[Xh6v,Yh6v,Zh6v] = HybridReconstruction(Fy.*Indi,1,HybridModel3);

%% R3D Hybrid model 2

pathExp   = '23-03-07 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Estereo_TSC_0_2';
HybridModelname = 'hybrid3_v_Fa';
HybridModel4 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
[Xh3v,Yh3v,Zh3v] = HybridReconstruction(Fy.*Indi,1,HybridModel4);

%% R3D Hybrid model - Pol1x Pol1y Frac2Z

pathExp   = '23-03-07 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Estereo_TSC_0_2';

HybridModelname = 'hybrid1_2frac_Fa';
HybridModel2frac = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
% [Fasesxa,FX] =  PhaseAdj(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)),5,1,[],1);
% [coefz,Ffr ] = Fracfit2D_1(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)));
% coefz(:,:,4) = coefz(:,:,1)*0;
coefz = HybridModel2frac.coefz;
Zh1f =  Eval_PhaseFrac(coefz, Fy);
Xh1f =  Eval_PhaseRegression(HybridModel2frac.coefx, Zh1f);
Yh1f =  Eval_PhaseRegression(HybridModel2frac.coefy, Zh1f);

Ind2 = NaN.*HybridModel2frac.N3; Ind2(HybridModel2frac.N3>10)=1;
Ind2 = Indi.*Ind2;
%%


resC =  1550;
resR =  1150;
offC = (size(Xh3,2) - resC)/2;
offR = (size(Xh3,1) - resR)/2;

d1 = Ind2(:,:,1).*NaN; d1(offR+(1:resR),offC+(1:resC)) = 1;

IndX = Ind2.*d1;

[Centers_S,  Radius_s  ,e_s  ,erms_s ]  = sphereFit(Xs.*IndX,Ys,Zs);
[Centers_h3, Radius_h3 ,e_h3 ,erms_h3 ] = sphereFit(Xh3  .*IndX,Yh3 ,Zh3 );
[Centers_h3v,Radius_h3v,e_h3v,erms_h3v] = sphereFit(Xh3v .*IndX,Yh3v,Zh3v );
[Centers_h6, Radius_h6 ,e_h6 ,erms_h6 ] = sphereFit(Xh6  .*IndX,Yh6 ,Zh6 );
[Centers_h6v,Radius_h6v,e_h6v,erms_h6v] = sphereFit(Xh6v .*IndX,Yh6v,Zh6v);
[Centers_h1f,Radius_h1f,e_h1f,erms_h1f] = sphereFit(Xh1f .*IndX,Yh1f,Zh1f);

%%
l1 = 520; l2 = 700;

Zaux = Zs.*IndX;
nn = shiftdim(sum((~isnan(Zaux.*IndX)),[1 2]));


cp1 = 100*shiftdim(sum((Zaux<l1),[1 2]))./nn;
cp2 = 100*shiftdim(sum((Zaux>l1).*(Zaux<l2),[1 2]))./nn;
cp3 = 100*shiftdim(sum((Zaux>l2),[1 2]))./nn;

tab1 = [cp1 cp2 cp3 erms_s(:) erms_h3(:) erms_h3v(:) erms_h6(:)  erms_h6v(:) erms_h1f(:)];

tab2 =[cp1 cp2 cp3 Radius_s(:) Radius_h3(:) Radius_h3v(:) Radius_h6(:)  Radius_h6v(:) Radius_h1f(:)];

return
%% PAra el articulo
rang = 0.6;
aa = 5;
nrows_fig = 1;
ncols_fig = 4;
aup = 0.03;
colMesh = turbo(255);
for a  =  1:7
index = 1:7;

    figure(901)
    gg = imagesc((e_s(:,:,a).*Indi(:,:,a))');
    gg.Parent.Color = 'none';
%     gg.Parent.FontSize = 11;
    axis equal, xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('u_c [px]')
    xlabel('v_c [px]')
%     gg.Parent.Title.String = {'Error map';'Traditional Method'};
    colormap(colMesh)
%     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
gg.Parent.FontWeight = 'bold';
    xlim([0.1 1199])
    ylim([0.1 1599])

    
    figure(902)
    gg = imagesc((e_h2f(:,:,a).*Indi(:,:,a))');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('u_c [px]')
    xlabel('v_c [px]')
%     gg.Parent.Title.String = {'Error map';'Proposed Method'};
    colormap(colMesh)
%     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';
    xlim([0.1 1199])
    ylim([0.1 1599])


   
    figure(903), hold off
    g2 = histogram(e_s(:,:,a)   ,-rang:0.01:rang); hold on
    g3 = histogram(e_h2f(:,:,a)  ,-rang:0.01:rang);


    g2.FaceColor = [0.8 0 0];
    g2.EdgeColor = 'none';
    g2.FaceAlpha =0.6;
    g2.LineStyle = 'none';
    g2.Orientation = 'vertical';


    g3.FaceColor = [0 0.8 0];
    g3.EdgeColor = 'none';
    g3.FaceAlpha =0.6;
    g3.LineStyle = 'none';
    g3.Orientation = 'vertical';

    
    g2.Parent.YLim = [0 8*10^4];
    g2.Parent.XLim = [-0.6 0.601];
    g2.Parent.XLabel.String = 'Error [mm]';
    g2.Parent.YLabel.String = 'Points';
    g2.Parent.FontSize = 16;
%     g2.Parent.XLabel.FontSize = 11;
%     g2.Parent.Title.String = 'Error histogram';
%     g.XAxis
%     leg = legend('Traditional','Proposed','FontSize',9);
%     leg.Orientation = 'horizontal';

    ff1 = figure(904);
    hold off



    figExt = showExtrinsics(StereoParams);
    for i = 1:numel(figExt.Children)

        if(strcmp(figExt.Children(i).Type,'patch'))
            figExt.Children(i-1).Visible = 'off';
            figExt.Children(i).Visible = 'off';
        end
%         figExt.Children(i).Type
        rotate(figExt.Children(i), [0 1 0], -90)
        if(strcmp(figExt.Children(i).Type,'patch') || strcmp(figExt.Children(i).Type,'line'))
          
        figExt.Children(i).XData = -figExt.Children(i).XData;

        end

        if(strcmp(figExt.Children(i).Type,'text') )
            figExt.Children(i).Position(1) = -figExt.Children(i).Position(1);

            if(strcmp(figExt.Children(i).String,'1') || strcmp(figExt.Children(i).String,'2'))
                figExt.Children(i).Visible = 'off';
            end

        end


    end
 hold on

 limsz = 190;
    Zsnorm = Zh2f(:,:,a).*Indi(:,:,a);
    Zsnorm = round(254* (Zsnorm-min(Zsnorm(:)))/(max(Zsnorm(:))-min(Zsnorm(:))))+1;
    Zsnorm(isnan(Zsnorm)) = 1;

    colors = flipud(parula(255));

    ColR = Zsnorm*0; ColG = ColR; ColB = ColR;

    ColR(:) = colors(Zsnorm,1);
    ColG(:) = colors(Zsnorm,2);
    ColB(:) = colors(Zsnorm,3);

    Col = cat(3,ColR,ColG,ColB);

    gs = mesh(Yh2f(1:aa:end,1:aa:end,a).*Indi(1:aa:end,1:aa:end,a), ...
        Zh2f(1:aa:end,1:aa:end,a),...
        Xh2f(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:).*Indi(1:aa:end,1:aa:end,a));
       hold on,

    Col2 = cat(3, 0*ColR+0.3, 0*ColG+0.3, 0*ColB+0.3);
    sombra = mesh(Yh2f(1:aa:end,1:aa:end,a).*Indi(1:aa:end,1:aa:end,a), ...
        Zh2f(1:aa:end,1:aa:end,a),...
        0*Xh2f(1:aa:end,1:aa:end,a)+limsz,uint8(255*Col(1:aa:end,1:aa:end,:)));


    xlabel(''), ylabel(''), zlabel('')
    title('')
    axis equal
    
    xlim([-130 130])
    zlim([-150 limsz])
    ylim([-100 850])


    [xsph,ysph,zsph] = sphere(30);

    xsph = Radius_h2f(a)*xsph+Centers_h2f(a,1);
    ysph = Radius_h2f(a)*ysph+Centers_h2f(a,2);
    zsph = Radius_h2f(a)*zsph+Centers_h2f(a,3);
    hold on,
    gsf = surf(ysph,zsph,xsph);
    gsf.FaceColor = 'None';
    gsf.EdgeAlpha = 0.4;


    aa = 2;
    Col = cat(3, 0*ysph+0.5, 0*ysph+0.5, 0*ysph+0.5);
    sombra2 = mesh(ysph(1:aa:end,1:aa:end), ...
        zsph(1:aa:end,1:aa:end),...
        0*xsph(1:aa:end,1:aa:end)+limsz,Col(1:aa:end,1:aa:end,:));



    [zcub,ycub] = meshgrid([500 700],[-300 300]);
    gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3;  gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
    gcub = surf(ycub*0-130,zcub,ycub); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
% 
% 
    [zcub,ycub] = meshgrid([701 801],[-300 300]);
    gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
    gcub = surf(ycub*0-130,zcub,ycub); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
% 
% 
    [zcub,ycub] = meshgrid([399 499],[-300 300]);
    gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;
    gcub = surf(ycub*0-130,zcub,ycub); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;

    

    gs.Parent.ZDir = 'reverse';
    gs.Parent.XDir = 'reverse';
    gs.Parent.FontSize = 13;
    gs.Parent.XAxis.LineWidth = 1.5;
    gs.Parent.YAxis.LineWidth = 1.5;
    gs.Parent.ZAxis.LineWidth = 1.5;
    gs.Parent.LineWidth = 1.5;
    gs.Parent.View = [-31.2078   30.2301];
    figExt.DataAspectRatio = [1 1 1];



    drawnow


    saveas(figure(901),sprintf('Exp2-Sphere SteError pose  %d',index(a)),'svg')
    saveas(figure(902),sprintf('Exp2-Sphere ProposedError pose %d',index(a)),'svg')
    saveas(figure(903),sprintf('Exp2-Sphere Histogram pose %d',index(a)),'svg')
    exportgraphics(figure(904),sprintf('Exp2-Sphere 3dPosition pose %d.png',index(a)),'resolution',500)

end



%%

rang = 0.6;
aa = 10;
nrows_fig = 2;
ncols_fig = 2;
aup = 0.03;
colMesh = turbo(255);
for a  =  1:7
    index = 1:16;
    figPri = figure(905); 
    figPri.Position = [155 96 1005 569];
%     cat(3,images(:,:,a)/255,images(:,:,a)/255,images(:,:,a)/255);
    znor = (e_s(:,:,a)-min(e_s(:,:,a),[],[1 2],'omitnan'))/(max(e_s(:,:,a),[],[1 2],'omitnan')-min(e_s(:,:,a),[],[1 2],'omitnan'));
    xnor = Xs(:,:,a)-mean(Xs(:,:,a),[1 2],'omitnan');
    ynor = Ys(:,:,a)-mean(Ys(:,:,a),[1 2],'omitnan');

    subplot(nrows_fig,ncols_fig,1), 
    gg = mesh(xnor, ...
              ynor, ...
              znor.*Indi(:,:,a)); 
    
    xl = Xs(:,:,a).*Indi(:,:,a);
    
   
    Nnorm = double(uint8(round(254*(e_s(:,:,a)+rang)/(2*rang)))+1);
    Nnorm(isnan(Nnorm)) = 1;

    ColR = Nnorm*0; ColG = ColR; ColB = ColR;
    ColR(:) = colMesh(Nnorm,1);
    ColG(:) = colMesh(Nnorm,2);
    ColB(:) = colMesh(Nnorm,3);
    Col1 = cat(3,ColR,ColG,ColB);


    gg.CDataMode = 'Manual';   
    gg.CData = Col1;
    gg.Parent.View = [90 -90];
    gg.Parent.XDir = 'reverse';
    gg.Parent.Color = 'none';
    gg.Parent.XAxis.Visible = 'off';
    gg.Parent.YAxis.Visible = 'off';
    gg.Parent.GridColor = 'none';
    axis equal

    gg.Parent.YLim = 1.05*[min(ynor,[],[1 2],'omitnan') max(ynor,[],[1 2],'omitnan')];
    %      gg.Parent.XLim = 1.5*[min(xnor,[],[1 2],'omitnan') max(xnor,[],[1 2],'omitnan')];
    %     gg.Parent.XLim = 2*[min(Ys(:,:,a),[],[1 2],'omitnan') max(Ys(:,:,a),[],[1 2],'omitnan')];
%     gg.Parent.YLim = [-95 95];

    gg.Parent.XLim = [-120 120];


    gg.Parent.Position(1) = 0.1;
    gg.Parent.Position(2) = gg.Parent.Position(2)-aup;
    gg.Parent.Position(4) = 1.1*gg.Parent.Position(4);

%     gg.Parent.ZLim=[-1 1];
    
%     cbgg = colorbar(gg.Parent,'Location','westoutside');
%     
%     cbgg.Ticks = 0:0.25:1;
%     cbgg.TickLabels = {'-0.6';'-0.3';'0';'0.3';'0.6'};
%     cbgg.FontSize = 10;
%     cbgg.Label.String = '[mm]';

%     gg.Parent.Position = [0.15    0.5838-aup   0.2134    0.3412];
%     cbgg.Position      = [0.12    0.615-aup    0.015    0.28];
%       cbgg.Position(1) = 0.12;
%       cbgg.Position      = [0.12 0.5838    0.0124    0.3186];

    gg.Parent.Title.String = {'Error map';'Traditional Method'};
    gg.Parent.Title.Position(1) = 0.80 *  gg.Parent.Title.Position(1);


    subplot(nrows_fig,ncols_fig,ncols_fig+1), 
    
    
    znor = (e_h2f(:,:,a)-min(e_h2f(:,:,a),[],[1 2],'omitnan'))/(max(e_h2f(:,:,a),[],[1 2],'omitnan')-min(e_h2f(:,:,a),[],[1 2],'omitnan'));
    xnor = Xh2f(:,:,a).*Indi(:,:,a)-mean(Xh2f(:,:,a).*Indi(:,:,a),[1 2],'omitnan');
    ynor = Yh2f(:,:,a).*Indi(:,:,a)-mean(Yh2f(:,:,a).*Indi(:,:,a),[1 2],'omitnan');

    gg2 = mesh(xnor, ...
               ynor, ...
               znor); 
    
    Nnorm = double(uint8(round(254*(e_h2f(:,:,a)+rang)/(2*rang)))+1);
    Nnorm(isnan(Nnorm)) = 1;

    ColR = Nnorm*0; ColG = ColR; ColB = ColR;
    ColR(:) = colMesh(Nnorm,1);
    ColG(:) = colMesh(Nnorm,2);
    ColB(:) = colMesh(Nnorm,3);
    Col = cat(3,ColR,ColG,ColB);

    gg2.CDataMode = 'Manual';   
    gg2.CData = Col;
    gg2.Parent.View = [90 -90];
    gg2.Parent.XDir = 'reverse';
    
    gg2.Parent.Color = 'none';
    gg2.Parent.XAxis.Visible = 'off';
    gg2.Parent.YAxis.Visible = 'off';
    gg2.Parent.GridColor = 'none';

    axis equal, %xlim([0 m_imageHeight]), ylim([0 m_imageWidth]), %colorbar
%     gg2.Parent.YLim = gg.Parent.XLim;
%     gg2.Parent.YLim = [-95 95];
    gg2.Parent.YLim = 1.05*[min(ynor,[],[1 2],'omitnan') max(ynor,[],[1 2],'omitnan')];
    gg2.Parent.XLim = [-120 120];


%     gg2.Parent.XLim = gg1.Parent.XLim;
%     gg2.Parent.ZLim=[-1 1];
    colormap(colMesh)

%     cbgg2 = colorbar(gg2.Parent,'Location','westoutside');
    
    

%     cbgg2.TicksMode = 'manual';
%     cbgg2.Ticks = linspace(0.0,1.0,9);
%     cbgg2.TickLabels = {'-0.6';'';'-0.3';'';'0';'';'0.3';'';'0.6'};
%     cbgg2.LimitsMode = 'auto';
%     cbgg2.Limits = [0 1];
%     cbgg2.FontSize = 10;
%     cbgg2.Label.String = '[mm]';
%     gg2.Parent.Position = [0.15    0.11-aup  0.2134    0.3412];
%     cbgg2.Position(1) = 0.12 ;
%     cbgg2.Position  = [0.12    0.1100    0.0123    0.3378];

% [0.12 0.5838    0.0124    0.3186];

    gg2.Parent.Title.String = {'Error map';'Proposed Method'};
    gg2.Parent.Position(1) = gg.Parent.Position(1);
    gg2.Parent.Position(4) = gg.Parent.Position(4);

    gg2.Parent.Title.Position(1) = 0.80 *  gg2.Parent.Title.Position(1);
    g=gca();
    %  g.FontSize = 14;
    % title(['Pose ',num2str(index(a))])


    subplot(nrows_fig,ncols_fig,2), hold off
    g2 = histogram(e_s(:,:,a)   ,-rang:0.01:rang); hold on
    g3 = histogram(e_h2f(:,:,a)  ,-rang:0.01:rang);


    g2.FaceColor = [0.8 0 0];
    g2.EdgeColor = 'none';
    g2.FaceAlpha =0.6;
    g2.LineStyle = 'none';
    g2.Orientation = 'vertical';


    g3.FaceColor = [0 0.8 0];
    g3.EdgeColor = 'none';
    g3.FaceAlpha =0.6;
    g3.LineStyle = 'none';
    g3.Orientation = 'vertical';

    g2.Parent.Position = [0.42    0.5838    0.2242    0.3412];

    colbar = colorbar;
    colbar.Position = [gg2.Parent.Position(1)*1.67     colbar.Position(2)*1.01   0.0150    0.8*gg2.Parent.Position(4)];
    colbar.Ticks = 0:0.25:1;
    colbar.TickLabels = {'-0.6';'-0.3';'0';'0.3';'0.6'};
    colbar.FontSize = 10;
    colbar.Label.String = '[mm]';

    
    
%     g2.Parent.YTickLabel = {};
    g2.Parent.YLim = [0 10*10^4];
    g2.Parent.XLim = [-0.6 0.65];
    g2.Parent.XLabel.String = 'Error [mm]';
    g2.Parent.YLabel.String = 'Points';
    g2.Parent.FontSize = 10;
    g2.Parent.XLabel.FontSize = 10;
    g2.Parent.Title.String = 'Error histogram';
%     g.XAxis
    leg = legend('Traditional','Proposed','FontSize',9);
    leg.Orientation = 'horizontal';
    leg.Position(1) = 0.422;
    leg.Position(2) = 0.890;


    
%     leg.Position = [g2.Parent.Position(1)    0.8839    0.2189    0.0299];
    ff1 = subplot(nrows_fig,ncols_fig,[ncols_fig+2]);
%     ff1.Position = [0.4 0.11 0.124 0.815];
    hold off
    Zsnorm = Zh2f(:,:,a).*Indi(:,:,a);
    Zsnorm = round(254* (Zsnorm-min(Zsnorm(:)))/(max(Zsnorm(:))-min(Zsnorm(:))))+1;
    Zsnorm(isnan(Zsnorm)) = 1;

    colors = flipud(parula(255));

    ColR = Zsnorm*0; ColG = ColR; ColB = ColR;

    ColR(:) = colors(Zsnorm,1);
    ColG(:) = colors(Zsnorm,2);
    ColB(:) = colors(Zsnorm,3);

    Col = cat(3,ColR,ColG,ColB);

    gs = mesh(Yh2f(1:aa:end,1:aa:end,a).*Indi(1:aa:end,1:aa:end,a), ...
        Zh2f(1:aa:end,1:aa:end,a),...
        -Xh2f(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:));
    hold on,
    xlabel('x [mm]'), ylabel('z [mm]'), zlabel('y [mm]')
    axis equal
    xlim([-150 150])
    zlim([-150 150])
    ylim([350 850])
    gs.Parent.Title.String = {'3D'};

    

    colbar2 = colorbar;
    colbar2.Units = 'Pixel';
    colbar2.Position(4) = [170.8270];
    colbar2.Units = 'normalized';
    colbar2.Position(1:3) =[gg2.Parent.Position(1)*1.67     colbar2.Position(2)*1.32   0.0150];    

    colbar2.Ticks = linspace(-200,200,5);
    colbar2.TickLabels = {'-0.6';'-0.3';'0';'0.3';'0.6'};
    colbar2.FontSize = 10;
    colbar2.Label.String = '[mm]';
    
    [xsph,ysph,zsph] = sphere(30);
    xsph = Radius_h2f(a)*xsph+Centers_h2f(a,1);
    ysph = Radius_h2f(a)*ysph+Centers_h2f(a,2);
    zsph = Radius_h2f(a)*zsph+Centers_h2f(a,3);
    hold on,
    gsf = surf(ysph,zsph,-xsph);
    gsf.FaceColor = 'None';
    gsf.EdgeAlpha = 0.4;
%     ff.Position = [ff.Position(1)*1.02 ff.Position(2)*0.25  1.3*ff.Position(3:4)] ;
    

    [xcub,ycub] = meshgrid(-200:400:200,-200:400:200);
    

    gcub = surf(xcub,xcub*0+500,ycub);
    gcub.FaceColor = 'r';
    gcub.FaceAlpha = 0.3;

    gcub2 = surf(xcub,xcub*0+700,ycub);
    gcub2.FaceColor = gcub.FaceColor;
    gcub2.FaceAlpha = gcub.FaceAlpha;
    ff1.View =  [-68.8455   25.6315];
    ff1.Position = [0.295    0.1100    0.4942    0.3412];
    gs.Parent.ZDir = 'reverse';
%     ff1.XLabel.Position = [0 350 -250];

    drawnow
    exportgraphics(figPri,sprintf('Exp2-Sphere StrereoVsProposed  pose %d.png',index(a)),'resolution',100)
%     exportgraphics(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'BackgroundColor','none','resolution',500)
%     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'svg')
%     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d',index(a)),'svg')
end




















%%
rang = 0.6;
aa = 10;
nrows_fig = 2;
ncols_fig = 5;

for a  =  1
    index = 1:7;
    figPri = figure(904); 
    figPri.Position = [-234 942 1740 489];
%     cat(3,images(:,:,a)/255,images(:,:,a)/255,images(:,:,a)/255);
    subplot(nrows_fig,ncols_fig,1), gg = mesh(images(:,:,a)'); 
    
    gg.CDataMode = 'Manual';   
    gg.CData = repmat(uint8(images(:,:,a)'),[1 1 3]);
    gg.Parent.View = [90 -90];
    gg.Parent.XDir = 'reverse';

    axis equal, xlim([0 m_imageHeight]), ylim([0 m_imageWidth]), %colorbar
    subplot(nrows_fig,ncols_fig,2), imagesc(e_s(:,:,a)) , caxis([-rang rang]),colormap default
    axis equal, xlim([0 m_imageWidth]), ylim([0 m_imageHeight])
    subplot(nrows_fig,ncols_fig,ncols_fig+1), imagesc(e_h2(:,:,a)), caxis([-rang rang])
    axis equal, xlim([0 m_imageWidth]), ylim([0 m_imageHeight]), %colorbar
    subplot(nrows_fig,ncols_fig,ncols_fig+2), imagesc(e_h2f(:,:,a)), caxis([-rang rang])
    axis equal, xlim([0 m_imageWidth]), ylim([0 m_imageHeight])


    % imagesc([e_s(:,:,a) e_h2(:,:,a); [e_h2f(:,:,a) NaN*e_h2f(:,:,a)]]), caxis([-0.5 0.5])

    g=gca();
    %  g.FontSize = 14;
    % title(['Pose ',num2str(index(a))])


    subplot(nrows_fig,ncols_fig,[3,ncols_fig+3]), hold off
    g2 = histogram(e_s(:,:,a)   ,-rang:0.0005:rang); hold on
    g3 = histogram(e_h2(:,:,a) ,-rang:0.0005:rang);
    g4 = histogram(e_h2f(:,:,a)  ,-rang:0.0005:rang);


    g2.FaceColor = [0.8 0 0];
    g2.EdgeColor = 'none';
    g2.FaceAlpha =0.6;
    g2.LineStyle = 'none';
    g2.Orientation = 'horizontal';


    g3.FaceColor = 'y';
    g3.EdgeColor = 'none';
    g3.FaceAlpha =0.6;
    g3.LineStyle = 'none';
    g3.Orientation = 'horizontal';


    g4.FaceColor = [0 0.8 0];
    g4.EdgeColor = 'none';
    g4.FaceAlpha =0.6;
    g4.LineStyle = 'none';
    g4.Orientation = 'horizontal';



    colbar = colorbar;
    colbar.Position = [0.4420    0.1108    0.0150    0.8127];
    colbar.Ticks = 0:0.25:1;
    colbar.TickLabels = {'-0.6';'-0.3';'0';'0.3';'0.6'};
    colbar.FontSize = 10;


    g=gca();
    g.FontSize = 11;
    g.YTickLabel = {};
    xlim([0 4000])
    g.XAxis
    legend('Stereo','Hybrid-Pol3','Hybrid-Rational','FontSize',10)

    ff1 = subplot(nrows_fig,ncols_fig,[4,ncols_fig+4]);
    ff1.Position = [0.638 0.11 0.124 0.815];
    hold off
    Zsnorm = Zs(:,:,a);
    Zsnorm = round(254* (Zsnorm-min(Zsnorm(:)))/(max(Zsnorm(:))-min(Zsnorm(:))))+1;
    Zsnorm(isnan(Zsnorm)) = 1;

    colors = flipud(jet(255));

    ColR = Zsnorm*0; ColG = ColR; ColB = ColR;

    ColR(:) = colors(Zsnorm,1);
    ColG(:) = colors(Zsnorm,2);
    ColB(:) = colors(Zsnorm,3);

    Col = cat(3,ColR,ColG,ColB);

    gs = mesh(Xh2f(1:aa:end,1:aa:end,a).*Indi(1:aa:end,1:aa:end,a), ...
        Zh2f(1:aa:end,1:aa:end,a),...
        Yh2f(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:));

    xlabel('x [mm]'), ylabel('z [mm]'), zlabel('y [mm]')
    axis equal
    xlim([-200 200])
    zlim([-200 200])
    ylim([0 900])

    [xsph,ysph,zsph] = sphere(30);
    xsph = Radius_h2f(a)*xsph+Centers_h2f(a,1);
    ysph = Radius_h2f(a)*ysph+Centers_h2f(a,2);
    zsph = Radius_h2f(a)*zsph+Centers_h2f(a,3);
    hold on,
    gsf = surf(xsph,zsph,ysph);

    gsf.FaceColor = 'None';
    gsf.EdgeAlpha = 0.2;
%     ff.Position = [ff.Position(1)*1.02 ff.Position(2)*0.25  1.3*ff.Position(3:4)] ;
    drawnow

    [xcub,ycub] = meshgrid(-200:400:200,-200:400:200);


    gcub = surf(xcub,xcub*0+500,ycub);
    gcub.FaceColor = 'r';
    gcub.FaceAlpha = 0.3;

    gcub2 = surf(xcub,xcub*0+700,ycub);
    gcub2.FaceColor = gcub.FaceColor;
    gcub2.FaceAlpha = gcub.FaceAlpha;
    ff1.View = [-23.22 41.1375];



    ff = subplot(nrows_fig,ncols_fig,[5,ncols_fig+5]);
    ff.Position = [0.8 0.16 0.1237 0.7150];
    hold off


    gs = mesh(Xh2f(1:aa:end,1:aa:end,a).*Indi(1:aa:end,1:aa:end,a), ...
        Zh2f(1:aa:end,1:aa:end,a),...
        Yh2f(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:));

    xlabel('x [mm]'), ylabel('z [mm]'), zlabel('y [mm]')
    axis equal
    xlim([-200 200])
    zlim([-200 200])
    ylim([0 900])

    [xsph,ysph,zsph] = sphere(30);
    xsph = Radius_h2f(a)*xsph+Centers_h2f(a,1);
    ysph = Radius_h2f(a)*ysph+Centers_h2f(a,2);
    zsph = Radius_h2f(a)*zsph+Centers_h2f(a,3);
    hold on,
    gsf = surf(xsph,zsph,ysph);

    gsf.FaceColor = 'None';
    gsf.EdgeAlpha = 0.2;
%     ff.Position = [ff.Position(1)*1.02 ff.Position(2)*0.25  1.3*ff.Position(3:4)] ;
    drawnow

    [xcub,ycub] = meshgrid(-200:400:200,-200:400:200);


    gcub = surf(xcub,xcub*0+500,ycub);
    gcub.FaceColor = 'r';
    gcub.FaceAlpha = 0.3;

    gcub2 = surf(xcub,xcub*0+700,ycub);
    gcub2.FaceColor = gcub.FaceColor;
    gcub2.FaceAlpha = gcub.FaceAlpha;
    ff.View = [0 90];


    saveas(figure(904),sprintf('PhaseErrorMaps Sphere1 Stereo - Coef02- pose %d.png',index(a)),'png')

end



