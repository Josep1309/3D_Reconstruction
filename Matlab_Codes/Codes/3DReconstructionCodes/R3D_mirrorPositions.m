%% Phases Lectures

pathExp   = '23-03-07 - Pruebas';
pathR3D = 'Mirror';

load(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_PhasesData.mat'],'Fx','Fy','MaskC','images')
% MaskC = Mask;
Indi = NaN*MaskC; Indi(MaskC>0) = 1;

%% Dividir data

index = [1 3 8];
Fx = Fx(:,:,index);
Fy = Fy(:,:,index);
Indi = Indi(:,:,index);
MaskC = MaskC(:,:,index);


%% R3D by Stereo model 

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


%% R3D Hybrid model 1


pathExp   = '23-03-07 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Estereo_TSC_0_2';

HybridModelname = 'hybrid3_1_Fa';

HybridModel1 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);

Ind2 = NaN.*HybridModel1.N3; Ind2(HybridModel1.N3>10)=1;
Ind2 = Indi.*Ind2;

[Xh1,Yh1,Zh1] = HybridReconstruction(Fy.*Indi,1,HybridModel1);

%% R3D Hybrid model 1 extended

HybridModelname = 'hybrid3_1v_2_Fa';
HybridModel1v = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
[Xh1v,Yh1v,Zh1v] = HybridReconstruction(Fy.*Indi,1,HybridModel1v,'POL3');

Ind3 = NaN.*HybridModel1v.N3; Ind3(HybridModel1.N3>10)=1;
Ind3 = Indi.*Ind3;

%% R3D Hybrid model 2

HybridModelname = 'hybrid3_2_Fa';
HybridModel2 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
[Xh2,Yh2,Zh2] = HybridReconstruction(Fy.*Indi,1,HybridModel2);



%% R3D Hybrid model 2 extended

HybridModelname = 'hybrid5_virtCorr_Fa';
HybridModel2v = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
[Xh2v,Yh2v,Zh2v] = HybridReconstruction(Fy.*Indi,1,HybridModel2v);

%% R3D Hybrid model 3

% pathExp   = '23-02-19 - Pruebas';
% pathSteCalib = 'WhiteBoard';
% StereoCalibNom = 'Estereo_TSC_0_3';
% 
% HybridModelname = 'hybrid_3_Fa';
% 
% HybridModel3 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
% 
% Ind4 = NaN.*HybridModel3.N3; Ind4(HybridModel3.N3>10)=1;
% % Ind4 = Indi.*Ind4;
% 
% [Xh3,Yh3,Zh3] = HybridReconstruction(Fy.*Indi,1,HybridModel3,'POL5');

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
Zh2f =  Eval_PhaseFrac(coefz, Fy);
Xh2f =  Eval_PhaseRegression(HybridModel2frac.coefx, Zh2f);
Yh2f =  Eval_PhaseRegression(HybridModel2frac.coefy, Zh2f);

Ind2 = NaN.*HybridModel2frac.N3; Ind2(HybridModel2frac.N3>10)=1;
Ind2 = Indi.*Ind2;

%% R3D Hybrid model - Pol1x Pol1y Frac2Z - ITERACION

pathExp   = '23-03-22 - Pruebas';
pathSteCalib = 'WhiteBoardExt';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Estereo_TSC_0_2';


HybridModelname = 'HybFracWB2_ite_Fa';
HybridModel2fracIT = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
% [Fasesxa,FX] =  PhaseAdj(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)),5,1,[],1);
% [coefz,Ffr ] = Fracfit2D_1(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)));
% coefz(:,:,4) = coefz(:,:,1)*0;
coefz = HybridModel2fracIT.coefz;

Zh2fi =  Eval_PhaseFrac(coefz, Fy);
Xh2fi =  Eval_PhaseRegression(HybridModel2fracIT.coefx, Zh2fi);
Yh2fi =  Eval_PhaseRegression(HybridModel2fracIT.coefy, Zh2fi);

Ind2 = NaN.*HybridModel2fracIT.N3; Ind2(HybridModel2fracIT.N3>10)=1;
Ind2 = Indi.*Ind2;

%% R3D Hybrid model - Pol1x Pol1y Frac2Z - ITERACION metodo Zhang

pathExp   = '23-03-07 - Pruebas';
pathSteCalib = 'Estereo';
HybridModelname = 'hybrid1_1frac_Fa_ite';
HybridModel1fracIT = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
% [Fasesxa,FX] =  PhaseAdj(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)),5,1,[],1);
% [coefz,Ffr ] = Fracfit2D_1(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)));
% coefz(:,:,4) = coefz(:,:,1)*0;
coefz = HybridModel1fracIT.coefz;

Zh1fi =  Eval_PhaseFrac(coefz, Fy);
Xh1fi =  Eval_PhaseRegression(HybridModel1fracIT.coefx, Zh1fi);
Yh1fi =  Eval_PhaseRegression(HybridModel1fracIT.coefy, Zh1fi);

Ind2 = NaN.*HybridModel1fracIT.N3; Ind2(HybridModel1fracIT.N3>10)=1;
Ind2 = Indi.*Ind2;

%%  Plane adjustment


resC =  1550;
resR =  1150;
offC = (size(Xh2f,2) - resC)/2;
offR = (size(Xh2f,1) - resR)/2;

d1 = Ind2(:,:,1).*NaN; d1(offR+(1:resR),offC+(1:resC)) = 1;

IndX = Ind2.*d1;

[e_s,erms_s,Ts] = Plane_fitting(Xs.*IndX,Ys,Zs,MaskC);
% [e_h1 ,erms_h1 ]  = Plane_fitting(Xh1  .*IndX,Yh1 ,Zh1 ,[],801);
% [e_h1v,erms_h1v]  = Plane_fitting(Xh1v .*IndX,Yh1v,Zh1v,[],802);
[e_h2 ,erms_h2 ]  = Plane_fitting(Xh2  .*IndX,Yh2 ,Zh2 ,[],803);
% [e_h2v,erms_h2v]  = Plane_fitting(Xh2v .*IndX,Yh2v,Zh2v,[],804);
[e_h2f,erms_h2f,Th2f]  = Plane_fitting(Xh2f .*IndX,Yh2f,Zh2f,[],805);
% [e_h2fi,erms_h2fi,Th2fi]  = Plane_fitting(Xh2fi .*IndX,Yh2fi,Zh2fi,[],805);
% [e_h1fi,erms_h1fi,Th1fi]  = Plane_fitting(Xh1fi .*IndX,Yh1fi,Zh1fi,[],805);
% [e_h3,erms_h3]  = Plane_fitting(Xh3 .*Ind2,Yh3,Zh3,[],805);


%% Incidence

l1 = 500; l2 = 700;

Zaux = Zs.*IndX;
nn = shiftdim(sum((~isnan(Zaux.*IndX)),[1 2]));


cp1 = 100*shiftdim(sum((Zaux<l1),[1 2]))./nn;
cp2 = 100*shiftdim(sum((Zaux>l1).*(Zaux<l2),[1 2]))./nn;
cp3 = 100*shiftdim(sum((Zaux>l2),[1 2]))./nn;



[cp1 cp2 cp3]
%% 



save(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_R3D-poses',num2str(index(1)),'-',num2str(index(end)),'.mat'], ...
                                                                    'Xh1','Yh1','Zh1', ...
                                                                    'Xs','Ys','Zs', ...
                                                                    'Xh2','Yh2','Zh2', ...
                                                                    'Xh1v','Yh1v','Zh1v', ...
                                                                    'Xh2v','Yh2v','Zh2v',...
                                                                    "e_s", "erms_s",...
                                                                    "e_h1", "erms_h1",...
                                                                    "e_h2", "erms_h2",...
                                                                    "e_h1v", "erms_h1v",...
                                                                    "e_h2v", "erms_h2v",...
                                                                    'Xh2f','Yh2f','Zh2f',...
                                                                    'e_h2f','erms_h2f');


save(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_R3D-poses',num2str(index(1)),'-',num2str(index(end)),'.mat']);


% save(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_R3D-poses',num2str(index(1)),'-',num2str(index(end)),'.mat'],'-append','Xs','Ys','Zs') 
%% Para el articulo

rang = 0.6;
aa = 5;
nrows_fig = 1;
ncols_fig = 4;
aup = 0.03;
colMesh = turbo(255);
for a  =  1:2
%     index = 1:16;
%     figPri = figure(918); 
%     figPri.Position = [155 96 1005 569];
%     cat(3,images(:,:,a)/255,images(:,:,a)/255,images(:,:,a)/255);
%     znor = (e_s(:,:,a)-min(e_s(:,:,a),[],[1 2],'omitnan'))/(max(e_s(:,:,a),[],[1 2],'omitnan')-min(e_s(:,:,a),[],[1 2],'omitnan'));

%     subplot(1,2,1), 
    figure(901)
%     gg = mesh(znor); 
    
    gg = imagesc(e_s(:,:,a)');
    gg.Parent.Color = 'none';
%     gg.Parent.FontSize = 11;
    axis equal, xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('u_c [px]')
    xlabel('v_c [px]')
    gg.Parent.Title.String = {'Error map';'Traditional Method'};
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
    

    
%     subplot(1,2,2), 
    figure(902)

    gg = imagesc(e_h2f(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('u_c [px]')
    xlabel('v_c [px]')
    gg.Parent.Title.String = {'Error map';'Proposed Method'};
    colormap(colMesh)
%     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
gg.Parent.FontWeight = 'bold';
%     znor = (e_h2f(:,:,a)-min(e_h2f(:,:,a),[],[1 2],'omitnan'))/(max(e_h2f(:,:,a),[],[1 2],'omitnan')-min(e_h2f(:,:,a),[],[1 2],'omitnan'));
%     gg2 = mesh(znor); 
%     
%     Nnorm = double(uint8(round(254*(e_h2f(:,:,a)+rang)/(2*rang)))+1);
%     Nnorm(isnan(Nnorm)) = 1;
% 
%     ColR = Nnorm*0; ColG = ColR; ColB = ColR;
%     ColR(:) = colMesh(Nnorm,1);
%     ColG(:) = colMesh(Nnorm,2);
%     ColB(:) = colMesh(Nnorm,3);
%     Col = cat(3,ColR,ColG,ColB);
% 
%     gg2.CDataMode = 'Manual';   
%     gg2.CData = Col;
%     gg2.Parent.View = [90 -90];
%     gg2.Parent.XDir = 'reverse';
%     
%     gg2.Parent.Color = 'none';
%     gg2.Parent.XAxis.Visible = 'on';
%     gg2.Parent.YAxis.Visible = 'on';
%     gg2.Parent.GridColor = 'none';
% 
%     axis equal, xlim([50 m_imageWidth-50]), ylim([50 m_imageHeight-50]), %colorbar
%     ylabel('u_c [px]')
%     xlabel('v_c [px]')
% 
%     gg2.Parent.XLim = gg.Parent.XLim;
%     gg2.Parent.Title.String = {'Error map';'Proposed Method'};
%     gg2.Parent.FontSize = 11;


   
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

    
    g2.Parent.YLim = [0 20*10^4];
    g2.Parent.XLim = [-0.6 0.65];
    g2.Parent.XLabel.String = 'Error [mm]';
    g2.Parent.YLabel.String = 'Points';
    g2.Parent.FontSize = 11;
    g2.Parent.XLabel.FontSize = 11;
    g2.Parent.Title.String = 'Error histogram';
%     g.XAxis
    leg = legend('Traditional','Proposed','FontSize',9);
    leg.Orientation = 'horizontal';

    ff1 = figure(904);
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

    Zsnorm = Zh2f(:,:,a);
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

    Col = cat(3, 0*ColR+0.3, 0*ColG+0.3, 0*ColB+0.3);
    sombra = mesh(Yh2f(1:aa:end,1:aa:end,a).*Indi(1:aa:end,1:aa:end,a), ...
        Zh2f(1:aa:end,1:aa:end,a),...
        0*Xh2f(1:aa:end,1:aa:end,a)+limsz,Col(1:aa:end,1:aa:end,:));
%     sombra.CDataSource = 0*Yh2f(1:aa:end,1:aa:end,a)+120;

 
%     xlabel('Y [mm]'), ylabel('Z [mm]'), zlabel('X [mm]')
    xlabel(''), ylabel(''), zlabel('')
    title('')
    axis equal
    
    xlim([-130 130])
    zlim([-150 limsz])
    ylim([-100 850])
%     gs.Parent.Title.String = {'3D Position'};

%     [xcub,ycub] = meshgrid(-200:400:200,-200:400:200);
%     gcub = surf(xcub,xcub*0+500,ycub);
%     gcub.FaceColor = 'r';
%     gcub.FaceAlpha = 0.3;



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
    gs.Parent.View = [-31.2078   30.2301];

    figExt.DataAspectRatio = [1 1 1];



    drawnow


%     saveas(figure(901),sprintf('Exp1-mirror SteError pose  %d',index(a)),'svg')
%     saveas(figure(902),sprintf('Exp1-mirror ProposedError pose %d',index(a)),'svg')
%     saveas(figure(903),sprintf('Exp1-mirror Histogram pose %d',index(a)),'svg')
%     exportgraphics(figure(904),sprintf('Exp1-mirror 3dPosition pose %d.png',index(a)),'resolution',500)



%     exportgraphics(figPri,sprintf('Exp2-Mirror StrereoVsProposed 2 pose %d.png',index(a)),'resolution',100)
%     exportgraphics(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'BackgroundColor','none','resolution',500)
%     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'svg')
%     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d',index(a)),'svg')
end











%% Only Stereo and Proposed
rang = 0.6;
aa = 10;
nrows_fig = 2;
ncols_fig = 2;
aup = 0.03;
colMesh = turbo(255);
for a  =  1
    index = 1:16;
    figPri = figure(908); 
    figPri.Position = [155 96 1005 569];
%     cat(3,images(:,:,a)/255,images(:,:,a)/255,images(:,:,a)/255);
    znor = (e_s(:,:,a)-min(e_s(:,:,a),[],[1 2],'omitnan'))/(max(e_s(:,:,a),[],[1 2],'omitnan')-min(e_s(:,:,a),[],[1 2],'omitnan'));

    subplot(nrows_fig,ncols_fig,1), 
    gg = mesh(znor); 
    
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
%     gg.Parent.Title.Position = [-50.6250  590    0.18];
    gg.Parent.Title.Position(1) = 0.4 *  gg.Parent.Title.Position(1);

    
    subplot(nrows_fig,ncols_fig,ncols_fig+1), 
    
    znor = (e_h2f(:,:,a)-min(e_h2f(:,:,a),[],[1 2],'omitnan'))/(max(e_h2f(:,:,a),[],[1 2],'omitnan')-min(e_h2f(:,:,a),[],[1 2],'omitnan'));
    gg2 = mesh(znor); 
    
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
    gg2.Parent.XLim = gg.Parent.XLim;


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
%    gg2.Parent.Title.Position = [-50.6250  590    0.18];
    gg2.Parent.Title.Position(1) = 0.4 *  gg2.Parent.Title.Position(1);

    % imagesc([e_s(:,:,a) e_h2(:,:,a); [e_h2f(:,:,a) NaN*e_h2f(:,:,a)]]), caxis([-0.5 0.5])

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

    g2.Parent.Position = [0.4108    0.5838    0.2242    0.3412];

    colbar = colorbar;
    colbar.Position = [gg2.Parent.Position(1)*1.67     colbar.Position(2)*1.01   0.0150    0.8*gg2.Parent.Position(4)];
    colbar.Ticks = 0:0.25:1;
    colbar.TickLabels = {'-0.6';'-0.3';'0';'0.3';'0.6'};
    colbar.FontSize = 10;
    colbar.Label.String = '[mm]';

    
    
%     g2.Parent.YTickLabel = {};
    g2.Parent.YLim = [0 20*10^4];
    g2.Parent.XLim = [-0.6 0.65];
    g2.Parent.XLabel.String = 'Error [mm]';
    g2.Parent.YLabel.String = 'Points';
    g2.Parent.FontSize = 10;
    g2.Parent.XLabel.FontSize = 10;
    g2.Parent.Title.String = 'Error histogram';
%     g.XAxis
    leg = legend('Traditional','Proposed','FontSize',9);
    leg.Orientation = 'horizontal';
    leg.Position(1) = 0.4135;
    leg.Position(2) = 0.890;
%     leg.Position = [g2.Parent.Position(1)    0.8839    0.2189    0.0299];
    ff1 = subplot(nrows_fig,ncols_fig,[ncols_fig+2]);
%     ff1.Position = [0.4 0.11 0.124 0.815];
    hold off
    Zsnorm = Zh2f(:,:,a);
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
    
%     [xsph,ysph,zsph] = sphere(30);
%     xsph = Radius_h2f(a)*xsph+Centers_h2f(a,1);
%     ysph = Radius_h2f(a)*ysph+Centers_h2f(a,2);
%     zsph = Radius_h2f(a)*zsph+Centers_h2f(a,3);
%     hold on,
%     gsf = surf(xsph,zsph,ysph);
%     gsf.FaceColor = 'None';
%     gsf.EdgeAlpha = 0.4;
%     ff.Position = [ff.Position(1)*1.02 ff.Position(2)*0.25  1.3*ff.Position(3:4)] ;
    

    [xcub,ycub] = meshgrid(-200:400:200,-200:400:200);
    

    gcub = surf(xcub,xcub*0+500,ycub);
    gcub.FaceColor = 'r';
    gcub.FaceAlpha = 0.3;

    gcub2 = surf(xcub,xcub*0+700,ycub);
    gcub2.FaceColor = gcub.FaceColor;
    gcub2.FaceAlpha = gcub.FaceAlpha;
    ff1.View = [-33.9715   33.3186];
    ff1.Position = [0.27    0.1100    0.4942    0.3412];
    gs.Parent.ZDir = 'reverse';
%     ff1.XLabel.Position = [0 350 -250];

    drawnow
%     exportgraphics(figPri,sprintf('Exp2-Mirror StrereoVsProposed 2 pose %d.png',index(a)),'resolution',100)
%     exportgraphics(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'BackgroundColor','none','resolution',500)
%     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'svg')
%     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d',index(a)),'svg')
end



















%% Compare the error maps

for a = 1:16
% a = 4; 
figure(904), 
subplot(1,2,1)
imagesc([e_s(:,:,a) e_h2(:,:,a); [e_h2f(:,:,a) NaN.*e_h2f(:,:,a)]]), caxis([-1 1])

 g=gca();
 g.FontSize = 14;
axis equal
ylim([0 2*1200])
title(['Pose ',num2str(index(a))])


rang = 1;
subplot(1,2,2), hold off

            g2 = histogram(e_s(:,:,a)   ,-rang:0.0005:rang); hold on
            g3 = histogram(e_h2(:,:,a) ,-rang:0.0005:rang);
            g4 = histogram(e_h2f(:,:,a)  ,-rang:0.0005:rang);
%             g5 = histogram(e_h2f(:,:,a)  ,-rang:0.0005:rang);
            
            g2.FaceColor = [1 0 0];
            g2.EdgeColor = [0.5 0.5 0];
            g2.FaceAlpha =0.6;
            g2.LineStyle = 'none';
            g2.Orientation = 'vertical';
            

            g3.FaceColor = 'y';
            g3.EdgeColor = [0.5 0.5 0];
            g3.FaceAlpha =0.6;
            g3.LineStyle = 'none';
            g3.Orientation = 'vertical';
            

            g4.FaceColor = [0 0.5 0.5];
            g4.EdgeColor = [0.5 0.5 0];
            g4.FaceAlpha =0.6;
            g4.LineStyle = 'none';
            g4.Orientation = 'vertical';

%             g5.FaceColor = [0 1 0];
%             g5.EdgeColor = [0.5 0.5 0];
%             g5.FaceAlpha =0.6;
%             g5.LineStyle = 'none';
%             g5.Orientation = 'vertical';
            
 g=gca();
 g.FontSize = 15;

legend('Stereo','H2-Pol3','H2-rational','H2-frac')
drawnow

% pause()
saveas(figure(904),sprintf('PhaseErrorMaps Mirror - pose 07-03 Ste-03Coef %d.png',index(a)),'png')
end


%% Comparing Stereo POL3 and Rational

rang = 1;
aa = 10;
nrows_fig = 2;
ncols_fig = 5;

writerObj = VideoWriter('Exp-Mirrors','MPEG-4');
writerObj.FrameRate = 1;
open(writerObj);

for a  =  1:16
    index = 1:16;
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
    colbar.Position = [0.4395    0.1108    0.0150    0.8127];
    colbar.Ticks = 0:0.25:1;
%     colbar.TickLabels = {'-0.6';'-0.3';'0';'0.3';'0.6'};
    colbar.TickLabels = {'-1.0';'-0.5';'0';'0.5';'1.0'};
    colbar.FontSize = 10;


    g=gca();
    g.FontSize = 11;
    g.YTickLabel = {};
    xlim([0 12000])
    g.XAxis
    title('Error Histograms')
    legend('Stereo','POLY-3','Rational','FontSize',10)

    ff1 = subplot(nrows_fig,ncols_fig,[4,ncols_fig+4]);
    hold off
%     title('3D position')




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
        rotate(figExt.Children(i), [0 1 0], 90)
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

        figExt.Children(i).Visible = 'off';
    end

    hold on

    ff1.Position = [0.638 0.11 0.124 0.815];
%     

    Zsnorm = Zs(:,:,a).*IndX(:,:,a);
    Zsnorm = round(254* (Zsnorm-min(Zsnorm(:)))/(max(Zsnorm(:))-min(Zsnorm(:))))+1;
    Zsnorm(isnan(Zsnorm)) = 1;

    colors = flipud(parula(255));


    ColR = Zsnorm*0; ColG = ColR; ColB = ColR;

    ColR(:) = colors(Zsnorm,1);
    ColG(:) = colors(Zsnorm,2);
    ColB(:) = colors(Zsnorm,3);

    Col = cat(3,ColR,ColG,ColB);

    gs = mesh(Yh2f(1:aa:end,1:aa:end,a).*IndX(1:aa:end,1:aa:end,a), ...
        Zh2f(1:aa:end,1:aa:end,a),...
        Xh2f(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:));


     Col2 = cat(3, 0*ColR+0.3, 0*ColG+0.3, 0*ColB+0.3);

    sombra = mesh(Yh2f(1:aa:end,1:aa:end,a).*IndX(1:aa:end,1:aa:end,a), ...
        Zh2f(1:aa:end,1:aa:end,a),...
        0*Xh2f(1:aa:end,1:aa:end,a)+200,uint8(255*Col2(1:aa:end,1:aa:end,:)));

    xlabel('x [mm]'), ylabel('z [mm]'), zlabel('y [mm]')
    axis equal
    xlim([-130 130])
    zlim([-150 limsz])
    ylim([-100 850])

    gs.Parent.View = [-31.2078   30.2301];


limsz = 200;
    
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

%     ff1.View = [-23.22 41.1375];

    aa = 2;
%     Col = cat(3, 0*ysph+0.5, 0*ysph+0.5, 0*ysph+0.5);
%     sombra2 = mesh(ysph(1:aa:end,1:aa:end), ...
%         zsph(1:aa:end,1:aa:end),...
%         0*xsph(1:aa:end,1:aa:end)-200,Col(1:aa:end,1:aa:end,:));

    title(['3D position - Pose ',num2str(a)])


drawnow




    ff = subplot(nrows_fig,ncols_fig,[5,ncols_fig+5]);
    ff.Position = [0.8 0.16 0.1237 0.7150];
    hold off
    Col = cat(3,ColR,ColG,ColB);

    gs = mesh(Yh2f(1:aa:end,1:aa:end,a).*Indi(1:aa:end,1:aa:end,a), ...
        Zh2f(1:aa:end,1:aa:end,a),...
        Xh2f(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:));

%     xlabel('x [mm]'), ylabel('z [mm]'), zlabel('y [mm]')
    axis equal
    xlim([-200 200])
    zlim([-200 200])
    ylim([0 900])

    title(['3D position Pose ',num2str(a)])
    ff.Visible = 'off';
    drawnow

%     [xcub,ycub] = meshgrid(-200:400:200,-200:400:200);
% 
% 
%     gcub = surf(xcub,xcub*0+500,ycub);
%     gcub.FaceColor = 'r';
%     gcub.FaceAlpha = 0.3;
% 
%     gcub2 = surf(xcub,xcub*0+700,ycub);
%     gcub2.FaceColor = gcub.FaceColor;
%     gcub2.FaceAlpha = gcub.FaceAlpha;
%     ff.View = [0 90];


    saveas(figure(904),sprintf('PhaseErrorMaps Mirror Stereo - Coef02- pose %d.png',index(a)),'png')
    frame = imread(sprintf('PhaseErrorMaps Mirror Stereo - Coef02- pose %d.png',index(a)));
    writeVideo(writerObj, frame);



end
close(writerObj);



