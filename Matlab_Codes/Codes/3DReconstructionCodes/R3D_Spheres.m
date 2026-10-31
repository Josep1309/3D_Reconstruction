

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

%% 
HybridModelname = 'hybrid3_2_Fa';
HybridModel2 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
[Xh2,Yh2,Zh2] = HybridReconstruction(Fy.*Indi,1,HybridModel2);

%% 
HybridModelname = 'hybrid5_virtCorr_Fa';
HybridModel2v = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
[Xh2v,Yh2v,Zh2v] = HybridReconstruction(Fy.*Indi,1,HybridModel2v);

%%
HybridModelname = 'hybrid1_2frac_Fa';
HybridModel2frac = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);


Zh2f =  Eval_PhaseFrac(HybridModel2frac.coefz, Fy);
Xh2f =  Eval_PhaseRegression(HybridModel2frac.coefx, Zh2f);
Yh2f =  Eval_PhaseRegression(HybridModel2frac.coefy, Zh2f);
%%
HybridModelname = 'hybrid1_2frac_Fa_ite';
HybridModel2frac_ite = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);


Zh2fi =  Eval_PhaseFrac(HybridModel2frac_ite.coefz, Fy);
Xh2fi =  Eval_PhaseRegression(HybridModel2frac_ite.coefx, Zh2fi);
Yh2fi =  Eval_PhaseRegression(HybridModel2frac_ite.coefy, Zh2fi);
%%
HybridModelname = 'hybrid1_1frac_Fa_ite';
HybridModel1frac_ite = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);


Zh1fi =  Eval_PhaseFrac(HybridModel1frac_ite.coefz, Fy);
Xh1fi =  Eval_PhaseRegression(HybridModel1frac_ite.coefx, Zh1fi);
Yh1fi =  Eval_PhaseRegression(HybridModel1frac_ite.coefy, Zh1fi);

%%

[Centers_S,  Radius_s  ,e_s  ,erms_s ] = sphereFit(Xs.*Indi,Ys,Zs);
[Centers_h2, Radius_h2 ,e_h2 ,erms_h2 ] = sphereFit(Xh2.*Indi ,Yh2 ,Zh2 );
% [Centers_h2v, Radius_h2v ,e_h2v ,erms_h2v ] = sphereFit(Xh2v.*Indi ,Yh2v ,Zh2v );
[Centers_h2f,Radius_h2f,e_h2f,erms_h2f] = sphereFit(Xh2f.*Indi,Yh2f,Zh2f);
% [Centers_h2fi,Radius_h2fi,e_h2fi,erms_h2fi] = sphereFit(Xh2fi.*Indi,Yh2fi,Zh2fi);
% [Centers_h1fi,Radius_h1fi,e_h1fi,erms_h1fi] = sphereFit(Xh1fi.*Indi,Yh1fi,Zh1fi);

%%
l1 = 500; l2 = 700;

Zaux = Zs.*Indi;
nn = shiftdim(sum((~isnan(Zaux.*Indi)),[1 2]));


cp1 = 100*shiftdim(sum((Zaux<l1),[1 2]))./nn;
cp2 = 100*shiftdim(sum((Zaux>l1).*(Zaux<l2),[1 2]))./nn;
cp3 = 100*shiftdim(sum((Zaux>l2),[1 2]))./nn;
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

    title('Captured Image')
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
    title('Stereo')

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
%     exportgraphics(figPri,sprintf('Exp2-Sphere StrereoVsProposed  pose %d.png',index(a)),'resolution',100)
%     exportgraphics(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'BackgroundColor','none','resolution',500)
%     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'svg')
%     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d',index(a)),'svg')
end




















%%
rang = 0.6;
aa = 10;
nrows_fig = 2;
ncols_fig = 5;

writerObj = VideoWriter('Exp-Spheres','MPEG-4');
writerObj.FrameRate = 1;
open(writerObj);
itt = 0;
for a  =  [1:3 7 4 5]
    itt = itt +1;
    index = 1:7;
    figPri = figure(904); 
    figPri.Position = [-234 942 1740 489];
%     cat(3,images(:,:,a)/255,images(:,:,a)/255,images(:,:,a)/255);
    subplot(nrows_fig,ncols_fig,1), gg = mesh(images(:,:,a)'); 
    title('Captured Image')

    gg.CDataMode = 'Manual';   
    gg.CData = repmat(uint8(images(:,:,a)'),[1 1 3]);
    gg.Parent.View = [90 -90];
    gg.Parent.XDir = 'reverse';

    axis equal, xlim([0 m_imageHeight]), ylim([0 m_imageWidth]), %colorbar
    subplot(nrows_fig,ncols_fig,2), imagesc(e_s(:,:,a)) , caxis([-rang rang]),colormap turbo
    title('Error map - Stereo')
    axis equal, xlim([0 m_imageWidth]), ylim([0 m_imageHeight])
    subplot(nrows_fig,ncols_fig,ncols_fig+1), imagesc(e_h2(:,:,a)), caxis([-rang rang])
        title('Error map - POLY-3')

    axis equal, xlim([0 m_imageWidth]), ylim([0 m_imageHeight]), %colorbar
    subplot(nrows_fig,ncols_fig,ncols_fig+2), imagesc(e_h2f(:,:,a)), caxis([-rang rang])
        title('Error map - Rational')

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


    g3.FaceColor = [0 0 0.8];
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
    title('Error Histograms')
    legend('Stereo','POLY-3','Rational','FontSize',10)

    ff1 = subplot(nrows_fig,ncols_fig,[4,ncols_fig+4]);
    hold off
%     title('3D position')




    figExt = showExtrinsics(StereoParams);
    % figExt.Position = [0.1300    0.1100    0.7750    0.8150];
    for i = 1:numel(figExt.Children)
        figExt.Children(i).Visible = 'off';
    end

    hold on

    ff1.Position = [0.638 0.11 0.124 0.815];

    Zsnorm = Zs(:,:,a);
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
        Xh2f(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:));
hold on,
     Col2 = cat(3, 0*ColR+0.3, 0*ColG+0.3, 0*ColB+0.3);
    sombra = mesh(Yh2f(1:aa:end,1:aa:end,a).*Indi(1:aa:end,1:aa:end,a), ...
        Zh2f(1:aa:end,1:aa:end,a),...
        0*Xh2f(1:aa:end,1:aa:end,a)+200,uint8(255*Col(1:aa:end,1:aa:end,:)));

    xlabel('x [mm]'), ylabel('z [mm]'), zlabel('y [mm]')
    axis equal
    limsz = 200;
     xlim([-130 200])
    zlim([-150 limsz])
    ylim([-100 850])

    [xsph,ysph,zsph] = sphere(30);
    xsph = Radius_h2f(a)*xsph+Centers_h2f(a,1);
    ysph = Radius_h2f(a)*ysph+Centers_h2f(a,2);
    zsph = Radius_h2f(a)*zsph+Centers_h2f(a,3);
    
    gsf = surf(ysph,zsph,xsph);

    gsf.FaceColor = 'None';
    gsf.EdgeAlpha = 0.2;
%     ff.Position = [ff.Position(1)*1.02 ff.Position(2)*0.25  1.3*ff.Position(3:4)] ;
    

   
    
    [zcub,ycub] = meshgrid([500 700],[-300 300]);
    gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3;  gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
    gcub = surf(ycub*0+200,zcub,ycub); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
% 
% 
    [zcub,ycub] = meshgrid([701 801],[-300 300]);
    gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
    gcub = surf(ycub*0+200,zcub,ycub); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
% 
% 
    [zcub,ycub] = meshgrid([399 499],[-300 300]);
    gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;
    gcub = surf(ycub*0+200,zcub,ycub); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;

    ff1.View = [-23.22 41.1375];


    aa = 2;
    Col = cat(3, 0*ysph+0.5, 0*ysph+0.5, 0*ysph+0.5);
    sombra2 = mesh(ysph(1:aa:end,1:aa:end), ...
        zsph(1:aa:end,1:aa:end),...
        0*xsph(1:aa:end,1:aa:end)+limsz,Col(1:aa:end,1:aa:end,:));

    title(['3D position Pose ',num2str(itt)])


drawnow

%     [zcub,ycub] = meshgrid([500 700],[-300 300]);
%     gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3;  gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
%     gcub = surf(ycub*0-130,zcub,ycub); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
% % 
% % 
%     [zcub,ycub] = meshgrid([701 801],[-300 300]);
%     gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3; gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
%     gcub = surf(ycub*0-130,zcub,ycub); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
% % 
% % 
%     [zcub,ycub] = meshgrid([399 499],[-300 300]);
%     gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;
%     gcub = surf(ycub*0-130,zcub,ycub); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.3;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;






    ff = subplot(nrows_fig,ncols_fig,[5,ncols_fig+5]);
    ff.Position = [0.8 0.16 0.1237 0.7150];
    hold off
    Col = cat(3,ColR,ColG,ColB);

    gs = mesh(Yh2f(1:aa:end,1:aa:end,a).*Indi(1:aa:end,1:aa:end,a), ...
        Zh2f(1:aa:end,1:aa:end,a),...
        Xh2f(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:));

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
    gsf = surf(ysph,zsph,xsph);

    gsf.FaceColor = 'None';
    gsf.EdgeAlpha = 0.2;
%     ff.Position = [ff.Position(1)*1.02 ff.Position(2)*0.25  1.3*ff.Position(3:4)] ;

    title('3D position')

    drawnow

    [xcub,ycub] = meshgrid(-200:400:200,-200:400:200);


    gcub = surf(xcub,xcub*0+500,ycub);
    gcub.FaceColor = 'r';
    gcub.FaceAlpha = 0.3;

    gcub2 = surf(xcub,xcub*0+700,ycub);
    gcub2.FaceColor = gcub.FaceColor;
    gcub2.FaceAlpha = gcub.FaceAlpha;
    ff.View = [0 90];





%     exportgraphics(figure(900),['I_',num2str(kk),'.png'],'Resolution',500)
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

    saveas(figure(904),sprintf('PhaseErrorMaps Sphere1 Stereo - Coef02- pose %d.png',index(a)),'png')
    frame = imread(sprintf('PhaseErrorMaps Sphere1 Stereo - Coef02- pose %d.png',index(a)));
    writeVideo(writerObj, frame);



end
close(writerObj);


