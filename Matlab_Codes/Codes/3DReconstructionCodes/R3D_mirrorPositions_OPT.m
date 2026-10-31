%% Phases Lectures

pathExp   = '23-05-05 - Pruebas';
pathR3D = 'Mirror';

load(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_PhasesData.mat'],'Fx','Fy','MaskC')
% MaskC = Mask;
Indi = NaN*MaskC; Indi(MaskC>0) = 1;

%% Dividir data

% index = [1 3 8];
% Fx = Fx(:,:,index);
% Fy = Fy(:,:,index);
% Indi = Indi(:,:,index);
% MaskC = MaskC(:,:,index);

%% R3D by Stereo model 

% Camera and projector resolutions
m_imageWidth = 1600;        %1936   %1280 ;     %2048
m_imageHeight = 1200;       %1464   %1024 ;     %1536
m_projectorWidth =  912;    %912    %1280;      %912
m_projectorHeight = 1140;   %1140   %800;       %1140


pathExp   = '23-05-05 - Pruebas';
pathSteCalib = 'Estereo';
StereoCalibNom = 'Ste_R0C00000P00000S00';
% StereoCalibNom = 'Estereo_TSC_0_2';

StereoType = 'BT';

if(strcmp(StereoType,'BT'))
    StereoParams = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'.mat']);
    typeCalib = 1;
else
    load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'.mat']);
    typeCalib = 3;

end


Fd = 'Fy';
res = [m_projectorHeight m_projectorWidth];


[Xs0,Ys0,Zs0] = StereoReconstruction(Fx,Fy,MaskC,18,StereoParams,typeCalib,Fd);


%% R3D by Stereo model 

% Camera and projector resolutions
m_imageWidth = 1600;        %1936   %1280 ;     %2048
m_imageHeight = 1200;       %1464   %1024 ;     %1536
m_projectorWidth =  912;    %912    %1280;      %912
m_projectorHeight = 1140;   %1140   %800;       %1140


pathExp   = '23-05-05 - Pruebas';
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
%% R3D Hybrid model - Pol1x Pol1y Frac2Z

pathExp   = '23-05-05 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Hybrid9ITE';

HybridModelname = 'm1_lc';
HybridModel2frac = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
% [Fasesxa,FX] =  PhaseAdj(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)),5,1,[],1);
% [coefz,Ffr ] = Fracfit2D_1(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)));
% coefz(:,:,4) = coefz(:,:,1)*0;
coefz = HybridModel2frac.coefz;
Z1 =  Eval_PhaseFrac(coefz, Fy);
X1 =  Eval_PhaseRegression(HybridModel2frac.coefx, Z1);
Y1 =  Eval_PhaseRegression(HybridModel2frac.coefy, Z1);

% Ind2 = NaN.*HybridModel2frac.N3; Ind2(HybridModel2frac.N3>10)=1;
% Ind2 = Indi.*Ind2;

%% R3D Hybrid model - Pol1x Pol1y Frac2Z

pathExp   = '23-05-05 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Hybrid9ITE';

HybridModelname = 'm2';
HybridModel2frac = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
% [Fasesxa,FX] =  PhaseAdj(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)),5,1,[],1);
% [coefz,Ffr ] = Fracfit2D_1(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)));
% coefz(:,:,4) = coefz(:,:,1)*0;
coefz = HybridModel2frac.coefz;
Z2 =  Eval_PhaseFrac(coefz, Fy);
X2 =  Eval_PhaseRegression(HybridModel2frac.coefx, Z2);
Y2 =  Eval_PhaseRegression(HybridModel2frac.coefy, Z2);

% Ind2 = NaN.*HybridModel2frac.N3; Ind2(HybridModel2frac.N3>10)=1;
% Ind2 = Indi.*Ind2;


%% R3D Hybrid model - Pol1x Pol1y Frac2Z

pathExp   = '23-05-05 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Hybrid9ITE';

HybridModelname = 'm3';
HybridModel2frac = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
% [Fasesxa,FX] =  PhaseAdj(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)),5,1,[],1);
% [coefz,Ffr ] = Fracfit2D_1(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)));
% coefz(:,:,4) = coefz(:,:,1)*0;
coefz = HybridModel2frac.coefz;
Z3 =  Eval_PhaseFrac(coefz, Fy);
X3 =  Eval_PhaseRegression(HybridModel2frac.coefx, Z3);
Y3 =  Eval_PhaseRegression(HybridModel2frac.coefy, Z3);

% Ind2 = NaN.*HybridModel2frac.N3; Ind2(HybridModel2frac.N3>10)=1;
% Ind2 = Indi.*Ind2;

%%  Plane adjustment


resC =  1550;
resR =  1150;
offC = (size(Xs,2) - resC)/2;
offR = (size(Xs,1) - resR)/2;

d1 = Indi(:,:,1).*NaN; d1(offR+(1:resR),offC+(1:resC)) = 1;

IndX = Indi.*d1;

[e_s0,erms_s0]     = Plane_fitting(Xs0.*IndX,Ys0,Zs0,MaskC);
[e_s,erms_s]     = Plane_fitting(Xs.*IndX,Ys,Zs,MaskC);
[e_h1,erms_h1]   = Plane_fitting(X1.*IndX,Y1,Z1,[],801);
[e_h2,erms_h2]   = Plane_fitting(X2.*IndX,Y2,Z2,[],801);
[e_h3,erms_h3]   = Plane_fitting(X3.*IndX,Y3,Z3,[],801);


%% Incidence

l1 = 520; l2 = 700;

Zaux = Zs.*IndX;
nn = shiftdim(sum((~isnan(Zaux.*IndX)),[1 2]));


cp1 = 100*shiftdim(sum((Zaux<l1),[1 2]))./nn;
cp2 = 100*shiftdim(sum((Zaux>l1).*(Zaux<l2),[1 2]))./nn;
cp3 = 100*shiftdim(sum((Zaux>l2),[1 2]))./nn;



tab1 = [cp1 cp2 cp3 erms_s0(:) erms_s(:) erms_h1(:) erms_h2(:) erms_h3(:)];

return
%% 



% save(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_R3D-poses',num2str(index(1)),'-',num2str(index(end)),'.mat'], ...
%                                                                     'Xh1','Yh1','Zh1', ...
%                                                                     'Xs','Ys','Zs', ...
%                                                                     'Xh2','Yh2','Zh2', ...
%                                                                     'Xh1v','Yh1v','Zh1v', ...
%                                                                     'Xh2v','Yh2v','Zh2v',...
%                                                                     "e_s", "erms_s",...
%                                                                     "e_h1", "erms_h1",...
%                                                                     "e_h2", "erms_h2",...
%                                                                     "e_h1v", "erms_h1v",...
%                                                                     "e_h2v", "erms_h2v",...
%                                                                     'Xh2f','Yh2f','Zh2f',...
%                                                                     'e_h2f','erms_h2f');
% 
% 
% save(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_R3D-poses',num2str(index(1)),'-',num2str(index(end)),'.mat']);
% 

% save(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_R3D-poses',num2str(index(1)),'-',num2str(index(end)),'.mat'],'-append','Xs','Ys','Zs') 
%% Para el articulo

%% Video

rang = 1;
aa = 5;
nrows_fig = 1;
ncols_fig = 4;
aup = 0.03;
colMesh = turbo(255);
figex = figure(1000);

figex.Position = [40 77   1117   583];
grabar = 0;

if(grabar)
    writerObj = VideoWriter('Mirror-OPT','MPEG-4');
    writerObj.FrameRate = 1;
    open(writerObj);
end

names = {'Stereo Lineal';'Stereo';'Method1';'Method2';'Method3'}

errormaps = {e_s0; e_s; e_h1;e_h2;e_h3};


order = 1:23;
for pose  =  1
    a = order(pose);
    %     index = 1:16;
    %     figPri = figure(918);
    %     figPri.Position = [155 96 1005 569];
    %     cat(3,images(:,:,a)/255,images(:,:,a)/255,images(:,:,a)/255);
    %     znor = (e_s(:,:,a)-min(e_s(:,:,a),[],[1 2],'omitnan'))/(max(e_s(:,:,a),[],[1 2],'omitnan')-min(e_s(:,:,a),[],[1 2],'omitnan'));

    subplot(2,3,1),
%     figure(901)
    %     gg = mesh(znor);

    gg = imagesc(errormaps{1}(:,:,a)');
    gg.Parent.Color = 'none';
    %     gg.Parent.FontSize = 11;
    axis equal, xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';names{1}};
    colormap(colMesh)
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';
    %     Nnorm = double(uint8(round(254*(e_s(:,:,a)+rang)/(2*rang)))+1);
    %     Nnorm(isnan(Nnorm)) = 1;
    %     ColR = Nnorm*0; ColG = ColR; ColB = ColR;
    %     ColR(:) = colMesh(Nnorm,1);
    %     ColG(:) = colMesh(Nnorm,2);
    %     ColB(:) = colMesh(Nnorm,3);
    %     Col1 = cat(3,ColR,ColG,ColB);
    %     gg.CDataMode = 'Manual';
    %     gg.CData = Col1;
    %     gg.Parent.View = [90 -90];
    %     gg.Parent.XDir = 'reverse';
    %     gg.Parent.XAxis.Visible = 'on';
    %     gg.Parent.YAxis.Visible = 'on';
    %     gg.Parent.GridColor = 'none';


    subplot(2,3,2)
    %     subplot(1,2,2),
%     figure(902)
    gg = imagesc(errormaps{2}(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';names{2}};
    colormap(colMesh)
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';



%     figure(9020)
    subplot(2,3,4),
    gg = imagesc(errormaps{3}(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';names{3}};
    colormap(colMesh)
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';


    %     figure(9021)
    subplot(2,3,5),
    gg = imagesc(errormaps{4}(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';names{4}};
    colormap(colMesh)
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';


%     figure(903), 
    subplot(2,3,3),hold off
     
    g2 = histogram(errormaps{1}(:,:,a)   ,-rang:0.01:rang,'DisplayName',names{1});hold on
    g3 = histogram(errormaps{2}(:,:,a)  ,-rang:0.01:rang,'DisplayName',names{2});
    g4 = histogram(errormaps{3}(:,:,a)  ,-rang:0.01:rang,'DisplayName',names{3});
    g5 = histogram(errormaps{4}(:,:,a)  ,-rang:0.01:rang,'DisplayName',names{4});
    
%     g5.Visible = 'off';
    
    grid on

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

    g4.FaceColor = [0 0 0.6];
    g4.EdgeColor = 'none';
    g4.FaceAlpha =0.6;
    g4.LineStyle = 'none';
    g4.Orientation = 'vertical';

    g5.FaceColor = [0.8 0.8 0];
    g5.EdgeColor = 'none';
    g5.FaceAlpha =0.6;
    g5.LineStyle = 'none';
    g5.Orientation = 'vertical';


    g2.Parent.YLim = [0 20*10^4];
    g2.Parent.XLim = [-rang rang*1.05];
    g2.Parent.XLabel.String = 'Error [mm]';
    g2.Parent.YLabel.String = 'Points';
    g2.Parent.FontSize = 16;
    g2.Parent.XLabel.FontSize = 16;
    g2.Parent.Title.String = 'Error histogram';
    g2.Parent.Title.Position(2) = g2.Parent.Title.Position(2)*1.1;

    %     g.XAxis
    leg = legend('FontSize',9,'Location','best');
    leg.Orientation = 'vertical';

    colormap(jet(256))
    colb = colorbar();
    colb.Position = [0.0600    0.4000    0.0164    0.3226];
    colb.Ticks = linspace(0,1,5);
    colb.TickLabels = {num2str(linspace(-rang,rang,5)')};


    subplot(2,3,6),
%     ff1 = figure(904);
    hold off



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
    hold on
    limsz = 190;

    Zsnorm = Zs(:,:,a).*IndX(:,:,a);
    Zsnorm = round(254* (Zsnorm-min(Zsnorm(:)))/(max(Zsnorm(:))-min(Zsnorm(:))))+1;
    Zsnorm(isnan(Zsnorm)) = 1;

    colors = flipud(parula(255));

    ColR = Zsnorm*0; ColG = ColR; ColB = ColR;

    ColR(:) = colors(Zsnorm,1);
    ColG(:) = colors(Zsnorm,2);
    ColB(:) = colors(Zsnorm,3);

    Col = cat(3,ColR,ColG,ColB);

    gs = mesh(Ys(1:aa:end,1:aa:end,a).*IndX(1:aa:end,1:aa:end,a), ...
        Zs(1:aa:end,1:aa:end,a),...
        Xs(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:).*IndX(1:aa:end,1:aa:end,a));
    hold on,

    Col = cat(3, 0*ColR+0.3, 0*ColG+0.3, 0*ColB+0.3);
    sombra = mesh(Ys(1:aa:end,1:aa:end,a).*IndX(1:aa:end,1:aa:end,a), ...
        Zs(1:aa:end,1:aa:end,a),...
        0*Xs(1:aa:end,1:aa:end,a)+limsz,Col(1:aa:end,1:aa:end,:));
    %     sombra.CDataSource = 0*Yh2f(1:aa:end,1:aa:end,a)+120;


        xlabel('Y [mm]'), ylabel('Z [mm]'), zlabel('X [mm]')
    title('')
    axis equal

    xlim([-130 130])
    zlim([-150 limsz])
    ylim([-100 850])
    gs.Parent.Title.String = {['3D Position Pose-',num2str(pose)]};
    
%     gs.Parent.Title.Position(2) = 1.1*gs.Parent.Title.Position(2);
    gs.Parent.Title.FontSize = 16;
    %     [xcub,ycub] = meshgrid(-200:400:200,-200:400:200);
    %     gcub = surf(xcub,xcub*0+500,ycub);
    %     gcub.FaceColor = 'r';
    %     gcub.FaceAlpha = 0.3;



    [zcub,ycub] = meshgrid([500 700],[-300 300]);
    gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.2;  gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
    gcub = surf(ycub*0-130,zcub,ycub); gcub.FaceColor = 'r';  gcub.FaceAlpha = 0.2; gcub.EdgeColor = 'r'; gcub.EdgeAlpha = 0.4;
    %
    %
    [zcub,ycub] = meshgrid([701 801],[-300 300]);
    gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.2; gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
    gcub = surf(ycub*0-130,zcub,ycub); gcub.FaceColor = 'g';  gcub.FaceAlpha = 0.2;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'g'; gcub.EdgeAlpha = 0.4;
    %
    %
    [zcub,ycub] = meshgrid([399 499],[-300 300]);
    gcub = surf(ycub,zcub,ycub*0+limsz); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.2;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;
    gcub = surf(ycub*0-130,zcub,ycub); gcub.FaceColor = 'b';  gcub.FaceAlpha = 0.2;gcub.EdgeColor = 'none'; gcub.EdgeColor = 'b'; gcub.EdgeAlpha = 0.4;



    %     gcub2 = surf(xcub,xcub*0+700,ycub);
    %     gcub2.FaceColor = gcub.FaceColor;
    %     gcub2.FaceAlpha = gcub.FaceAlpha;
    %     view(-33.9715,   33.3186);
    gs.Parent.ZDir = 'reverse';
    gs.Parent.XDir = 'reverse';
    gs.Parent.FontSize = 13;
    gs.Parent.XAxis.LineWidth = 1.5;
    gs.Parent.YAxis.LineWidth = 1.5;
    gs.Parent.ZAxis.LineWidth = 1.5;
    gs.Parent.LineWidth = 1.5;
    gs.Parent.View = [-15.6516   19.4301];

    figExt.DataAspectRatio = [1 1 1];



    drawnow


    if(grabar)
        saveas(figure(1000),sprintf('PhaseErrorMaps MirrorOPT Stereo - Coef02- pose %d.png',pose),'png')
        frame = imread(sprintf('PhaseErrorMaps MirrorOPT Stereo - Coef02- pose %d.png',pose));
        writeVideo(writerObj, frame);
    end

%         saveas(figure(901),sprintf('Exp1-mirror SteError pose  %d',pose),'svg')
%         saveas(figure(902),sprintf('Exp1-mirror POL6-V pose %d',pose),'svg')
%         saveas(figure(9020),sprintf('Exp1-mirror POL3-E pose %d',pose),'svg')
%         saveas(figure(9021),sprintf('Exp1-mirror POL6-E pose  %d',pose),'svg')
%         saveas(figure(903),sprintf('Exp1-mirror Histogram pose %d',pose),'svg')
%         exportgraphics(figure(904),sprintf('Exp1-mirror 3D pose %d.png',pose),'resolution',500)



    %     exportgraphics(figPri,sprintf('Exp2-Mirror StrereoVsProposed 2 pose %d.png',index(a)),'resolution',100)
    %     exportgraphics(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'BackgroundColor','none','resolution',500)
    %     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'svg')
    %     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d',index(a)),'svg')
end

if(grabar)
close(writerObj);
end
















