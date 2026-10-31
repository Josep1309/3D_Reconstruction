%% Phases Lectures

pathExp   = '23-03-07 - Pruebas';
pathR3D = 'Sphere3';

load(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_PhasesData.mat'],'Fx','Fy','MaskC','images')
% MaskC = Mask;
% Para OLEN Sphere3 y phasesData2


MaskC([1:15 end-15:end],:,:) = 0;
MaskC(:,[1:15 end-15:end],:) = 0;
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
resC =  1550;
resR =  1150;
offC = (size(Xs,2) - resC)/2;
offR = (size(Xs,1) - resR)/2;

d1 = Indi(:,:,1).*NaN; d1(offR+(1:resR),offC+(1:resC)) = 1;

IndX = Indi.*d1;

[Centers_S,  Radius_s  ,e_s  ,erms_s ]  = sphereFit(Xs.*IndX,Ys,Zs);
%% R3D Hybrid Pol3 fase -> (X,Y,Z) 

pathExp   = '23-03-07 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Estereo_TSC_0_2';
for i = 1:4
    HybridModelname = ['hybrid',num2str(i+2),'_5_Vr'];
    HybridModel1 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
    [Xh3,Yh3,Zh3] = HybridReconstruction(Fy.*Indi,1,HybridModel1);
    
    Xf1{i} = Xh3; Yf1{i} = Yh3; Zf1{i} = Zh3;
    [Centers_h3, Radius_h3 ,e_h3 ,erms_h3 ] = sphereFit(Xh3  .*IndX,Yh3 ,Zh3);
    erms_f1(:,i) = erms_h3(:);
    Radius_f1(:,i) = Radius_h3(:);
    Centers_h1(:,:,i) = Centers_h3;
    e_h1{i} = e_h3;

end

%% R3D Hybrid Pol3 fase -> (X,Y,Z) 

pathExp   = '23-03-07 - Pruebas';
pathSteCalib = 'Estereo';
% StereoCalibNom = 'Ste_R0C11111P00000S00';
StereoCalibNom = 'Estereo_TSC_0_2';
for i = 1:4
    HybridModelname = ['hybrid',num2str(i+2),'_2_Fa'];
    HybridModel1 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);

    [Xh3,Yh3,Zh3] = HybridReconstruction(Fy.*Indi,1,HybridModel1);

    Xf2{i} = Xh3; Yf2{i} = Yh3; Zf2{i} = Zh3;
    [Centers_h3, Radius_h3 ,e_h3 ,erms_h3 ] = sphereFit(Xh3  .*IndX,Yh3 ,Zh3);

    erms_f2(:,i) = erms_h3(:);
    Radius_f2(:,i) = Radius_h3(:);
    e_h2{i} = e_h3;

end

%% R3D Hybrid Pol3 fase -> (X,Y,Z) 
% 
% pathExp   = '23-03-07 - Pruebas';
% pathSteCalib = 'Estereo';
% % StereoCalibNom = 'Ste_R0C11111P00000S00';
% StereoCalibNom = 'Estereo_TSC_0_2';
% for i = 1:4
%     HybridModelname = ['hybrid',num2str(i+2),'_6_Vr'];
%     HybridModel1 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
% 
%     Z = Eval_PhaseRegression(HybridModel1.coefz, Fy.*Indi);  
%     X = Eval_PhaseRegression(HybridModel1.coefx, Z);
%     Y = Eval_PhaseRegression(HybridModel1.coefy, Z);
% 
%     Xf2{i} = X; Yf2{i} = Y; Zf2{i} = Z;
%     [Centers_h3, Radius_h3 ,e_h3 ,erms_h3 ] = sphereFit(X  .*IndX,Y ,Z);
% 
%     erms_f2(:,i) = erms_h3(:);
%     Radius_f2(:,i) = Radius_h3(:);
% end



%% R3D Hybrid model - Pol1x Pol1y Frac2Z

% pathExp   = '23-03-07 - Pruebas';
% pathSteCalib = 'Estereo';
% % StereoCalibNom = 'Ste_R0C11111P00000S00';
% StereoCalibNom = 'Estereo_TSC_0_2';
% 
% HybridModelname = 'hybrid1_2frac_Fa';
% HybridModel2frac = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
% % [Fasesxa,FX] =  PhaseAdj(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)),5,1,[],1);
% % [coefz,Ffr ] = Fracfit2D_1(HybridModel2frac.coefz(:,:,1:3),~isnan(HybridModel2frac.coefz(:,:,1:3)));
% % coefz(:,:,4) = coefz(:,:,1)*0;
% coefz = HybridModel2frac.coefz;
% Zh1f =  Eval_PhaseFrac(coefz, Fy);
% Xh1f =  Eval_PhaseRegression(HybridModel2frac.coefx, Zh1f);
% Yh1f =  Eval_PhaseRegression(HybridModel2frac.coefy, Zh1f);
% 
% Ind2 = NaN.*HybridModel2frac.N3; Ind2(HybridModel2frac.N3>10)=1;
% Ind2 = Indi.*Ind2;
% [Centers_h1f, Radius_h1f ,e_h1f ,erms_h1f ] = sphereFit(Xh1f .*IndX,Yh1f,Zh1f);

%% Incidence

l1 = 520; l2 = 700;

Zaux = Zs.*IndX;
nn = shiftdim(sum((~isnan(Zaux.*IndX)),[1 2]));


cp1 = 100*shiftdim(sum((Zaux<l1),[1 2]))./nn;
cp2 = 100*shiftdim(sum((Zaux>l1).*(Zaux<l2),[1 2]))./nn;
cp3 = 100*shiftdim(sum((Zaux>l2),[1 2]))./nn;



tab1 = [cp1 cp2 cp3 erms_s(:) erms_f1 erms_f2 ];
tab2 = [cp1 cp2 cp3 Radius_s(:) Radius_f1 Radius_f2 ];

return
%% 





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


% save(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_R3D-poses',num2str(index(1)),'-',num2str(index(end)),'.mat'],'-append','Xs','Ys','Zs') 
%% Para el articulo

rang =2;
aa = 5;
nrows_fig = 1;
ncols_fig = 4;
aup = 0.03;
colMesh = turbo(255);

for pose  =  1
    a = order(pose);
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
    axis equal, 
    
    st =  regionprops(IndX(:,:,a)>0, 'BoundingBox' );
    st = st.BoundingBox;


    ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar



    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'Stereo'};
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
    gg = imagesc(e_h1{4}(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, 
    ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'POL6-V'};
    colormap(colMesh)
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';



    figure(90213)
    gg = imagesc(e_h1{1}(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, 
    ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'POL3-V'};
    colormap(colMesh)
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';
% 
% 
% 
%     figure(9020)
%     gg = imagesc(e_h2{1}(:,:,a)');
%     gg.Parent.Color = 'none';
%     gg.Parent.FontSize = 11;
%     axis equal,     ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar
% 
%     ylabel('$u_c$ [px]','Interpreter','latex')
%     xlabel('$v_c$ [px]','Interpreter','latex')
%     gg.Parent.Title.String = {'Error map';'POL3-E'};
%     colormap(colMesh)
%     %     colorbar
%     caxis([-rang rang+0.002])
%     gg.Parent.FontSize = 15;
%     gg.Parent.FontWeight = 'bold';
% 
% 
    figure(9021)
    gg = imagesc(e_h2{4}(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, 
    ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'POL6-E'};
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

%     g3 = histogram(e_h1{4}(:,:,a)+Radius_f1(a,4)  ,98+(-rang:0.01:rang),'DisplayName', ...
%         ['POL6-V.', ' Mean : ', sprintf('%3.3f',Radius_f1(a,4)),'. Rmse :', sprintf('%3.3f',erms_f1(a,4))]); hold on
%     g2 = histogram(e_s(:,:,a)+Radius_s(a)   ,98+(-rang:0.01:rang),'DisplayName', ...
%         ['Stereo.', ' Mean : ', sprintf('%3.3f',Radius_s(a)),'. Rmse :', sprintf('%3.3f',erms_s(a))]);
%     g4 = histogram(e_h2{1}(:,:,a)+Radius_f2(a,1)  ,98+(-rang:0.01:rang),'DisplayName', ...
%         ['POL3-E.', ' Mean : ', sprintf('%3.3f',Radius_f2(a,1)),'. Rmse :', sprintf('%3.3f',erms_f2(a,1))]);


 
    g2 = histogram(e_s(:,:,a)   ,-rang:0.01:rang,'DisplayName', ...
        ['Stereo.', ' Rmse :', sprintf('%3.3f',erms_s(a))]);
    hold on
    g4 = histogram(e_h2{1}(:,:,a)  ,-rang:0.01:rang,'DisplayName', ...
        ['POL3-E', ' Rmse :', sprintf('%3.3f',erms_f2(a,1))]);

   
    g6 = histogram(e_h1{1}(:,:,a)  ,-rang:0.01:rang,'DisplayName', ...
        ['POL3-V',' Rmse :', sprintf('%3.3f',erms_f1(a,1))]);
    g5 = histogram(e_h2{4}(:,:,a)  ,-rang:0.01:rang,'DisplayName', ...
        ['POL6-E',' Rmse :', sprintf('%3.3f',erms_f2(a,4))]);
    g3 = histogram(e_h1{4}(:,:,a)  ,-rang:0.01:rang,'DisplayName', ...
        ['POL6-V',' Rmse :', sprintf('%3.3f',erms_f1(a,4))]);
    


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

    g6.FaceColor = 'c';
    g6.EdgeColor = 'none';
    g6.FaceAlpha =0.6;
    g6.LineStyle = 'none';
    g6.Orientation = 'vertical';


    g2.Parent.YLim = [0 10*10^4];
    g2.Parent.XLim = [-rang rang*1.005];
    g2.Parent.XLabel.String = 'Error [mm]';
    g2.Parent.YLabel.String = 'Points';
    g2.Parent.FontSize = 16;
    g2.Parent.XLabel.FontSize = 16;
    g2.Parent.Title.String = 'Error Histograms';


    %     g.XAxis
    leg = legend('FontSize',9,'Location','best');
    leg.Orientation = 'vertical';
    leg.FontSize = 12;


    ffcb = figure(9040), hold off


    x1 = e_h1{4}(:,:,a)+Radius_f1(a,4);
    x1 = x1(~isnan(x1));

    x2 = e_s(:,:,a)+Radius_s(a);
    x2 = x2(~isnan(x2));

    x3 = e_h2{1}(:,:,a)+Radius_f2(a,1);
    x3 = x3(~isnan(x3));

    boxplot([x2,x1,x3],'Notch','on','OutlierSize',1,'Labels',{'Stereo','POL6-V','POL3-E'});
    ffcb.Children.YLabel.String = 'Radius [mm]';
    ffcb.Children.FontSize = 16;
    ffcb.Children.XLabel.FontSize = 16;
%     ffcb.Children.Title.String = 'Estimated Radius';
%     ylim([90 100])
    hold on
    plot(0:3, [98 98 98 98],'--r','LineWidth',1.5)
    legend('Reference Radius','Location','best')

    grid on

%     plot()
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

    Zsnorm = Zf1{4}(:,:,a).*IndX(:,:,a);
    Zsnorm = round(254* (Zsnorm-min(Zsnorm(:)))/(max(Zsnorm(:))-min(Zsnorm(:))))+1;
    Zsnorm(isnan(Zsnorm)) = 1;

    colors = flipud(parula(255));

    ColR = Zsnorm*0; ColG = ColR; ColB = ColR;

    ColR(:) = colors(Zsnorm,1);
    ColG(:) = colors(Zsnorm,2);
    ColB(:) = colors(Zsnorm,3);

    Col = cat(3,ColR,ColG,ColB);

    gs = mesh(Yf1{4}(1:aa:end,1:aa:end,a).*IndX(1:aa:end,1:aa:end,a), ...
        Zf1{4}(1:aa:end,1:aa:end,a),...
        Xf1{4}(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:).*IndX(1:aa:end,1:aa:end,a));
    hold on,

    Col = cat(3, 0*ColR+0.3, 0*ColG+0.3, 0*ColB+0.3);
    sombra = mesh(Yf1{4}(1:aa:end,1:aa:end,a).*IndX(1:aa:end,1:aa:end,a), ...
        Zf1{4}(1:aa:end,1:aa:end,a),...
        0*Xf1{4}(1:aa:end,1:aa:end,a)+limsz,Col(1:aa:end,1:aa:end,:));
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


    [xsph,ysph,zsph] = sphere(30);

    xsph = Radius_f1(a,4)*xsph+Centers_h1(a,1,4);
    ysph = Radius_f1(a,4)*ysph+Centers_h1(a,2,4);
    zsph = Radius_f1(a,4)*zsph+Centers_h1(a,3,4);
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


%         saveas(figure(901),sprintf('Exp2-Sphere SteError pose  %d',pose),'svg')
%         saveas(figure(902),sprintf('Exp2-Sphere POL6-V pose %d',pose),'svg')
%         saveas(figure(9020),sprintf('Exp2-Sphere POL3-E pose %d',pose),'svg')
%         saveas(figure(9021),sprintf('Exp2-Sphere POL6-E pose  %d',pose),'svg')
        saveas(figure(903),sprintf('Exp2-Sphere Histogram pose %d',pose),'svg')
%         saveas(figure(9040),sprintf('Exp2-Sphere CajayBig pose %d',pose),'svg')



%         exportgraphics(figure(901),sprintf('Exp2-Sphere SteError pose %d.png',pose),'resolution',500)
%         exportgraphics(figure(902),sprintf('Exp2-Sphere POL6-V pose %d.png',pose),'resolution',500)
%         exportgraphics(figure(90213),sprintf('Exp2-Sphere POL3-V pose %d.png',pose),'resolution',500)
%         exportgraphics(figure(9020),sprintf('Exp2-Sphere POL3-E pose %d.png',pose),'resolution',500)
%         exportgraphics(figure(9021),sprintf('Exp2-Sphere POL6-E pose %d.png',pose),'resolution',500)
%         exportgraphics(figure(9040),sprintf('Exp2-Sphere CajayBig pose %d.png',pose),'resolution',500)

%         exportgraphics(figure(904),sprintf('Exp1-Sphere 3D pose %d.png',pose),'resolution',500)



    %     exportgraphics(figPri,sprintf('Exp2-Mirror StrereoVsProposed 2 pose %d.png',index(a)),'resolution',100)
    %     exportgraphics(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'BackgroundColor','none','resolution',500)
    %     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d.png',index(a)),'svg')
    %     saveas(figPri,sprintf('Exp2-Shperes StrereoVsProposed pose %d',index(a)),'svg')
end





%% Video 



rang = 2;
aa = 5;
nrows_fig = 1;
ncols_fig = 4;
aup = 0.03;
colMesh = turbo(255);
figex = figure(1000);

% figex.Position = [ -109         786        1243         972];
figex.Position = [1367        -311        1920        1003];

grabVid = 1;

if(grabVid)
    writerObj = VideoWriter('Sphere-OLEN_5em','MPEG-4');
    writerObj.FrameRate = 1;
    open(writerObj);
end
order = 1:7;
for pose  =  1:7
    a = order(pose);
    %     index = 1:16;
    %     figPri = figure(918);
    %     figPri.Position = [155 96 1005 569];
    %     cat(3,images(:,:,a)/255,images(:,:,a)/255,images(:,:,a)/255);
    %     znor = (e_s(:,:,a)-min(e_s(:,:,a),[],[1 2],'omitnan'))/(max(e_s(:,:,a),[],[1 2],'omitnan')-min(e_s(:,:,a),[],[1 2],'omitnan'));

    g1 = subplot(2,4,1),
    g1.Position(2) = 0.4    
%     figure(901)
    %     gg = mesh(znor);
st =  regionprops(IndX(:,:,a)>0, 'BoundingBox' );
    st = st.BoundingBox;
    
    gg = imagesc(e_s(:,:,a)');
    gg.Parent.Color = 'none';
    %     gg.Parent.FontSize = 11;
    axis equal, %xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'Stereo'};
    colormap(colMesh)
    ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar
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


    subplot(2,4,3)
    %     subplot(1,2,2),
%     figure(902)
    gg = imagesc(e_h1{1}(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, %xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'POL3-V'};
    colormap(colMesh)
    ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';



    subplot(2,4,7)
    %     subplot(1,2,2),
%     figure(902)
    gg = imagesc(e_h1{4}(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, %xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'POL6-V'};
    colormap(colMesh)
    ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';



%     figure(9020)
    subplot(2,4,2),
    gg = imagesc(e_h2{1}(:,:,a)');
   
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'POL3-E'};
    colormap(colMesh)
     ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';


    

    %     figure(9021)
    subplot(2,4,6),
    gg = imagesc(e_h2{4}(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, %xlim([50 m_imageHeight-50]), ylim([50 m_imageWidth-50]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'POL6-E'};
    colormap(colMesh)
     ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';


%     figure(903), 
    subplot(2,4,4), hold off
     
    g2 = histogram(e_s(:,:,a)   ,-rang:0.01:rang,'DisplayName', ...
        ['Stereo.', ' Rmse :', sprintf('%3.3f',erms_s(a))]);
    hold on
    g4 = histogram(e_h2{1}(:,:,a)  ,-rang:0.01:rang,'DisplayName', ...
        ['POL3-E', ' Rmse :', sprintf('%3.3f',erms_f2(a,1))]);

   
    g6 = histogram(e_h1{1}(:,:,a)  ,-rang:0.01:rang,'DisplayName', ...
        ['POL3-V',' Rmse :', sprintf('%3.3f',erms_f1(a,1))]);
    g5 = histogram(e_h2{4}(:,:,a)  ,-rang:0.01:rang,'DisplayName', ...
        ['POL6-E',' Rmse :', sprintf('%3.3f',erms_f2(a,4))]);
    g3 = histogram(e_h1{4}(:,:,a)  ,-rang:0.01:rang,'DisplayName', ...
        ['POL6-V',' Rmse :', sprintf('%3.3f',erms_f1(a,4))]);
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

    g6.FaceColor = 'c';
    g6.EdgeColor = 'none';
    g6.FaceAlpha =0.6;
    g6.LineStyle = 'none';
    g6.Orientation = 'vertical';


    g2.Parent.YLim = [0 10*10^4];
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
    colb.TickLabels = {'-2';'-1';'0';'1';'2'};
    colb.Label.String ={'mm'};
%     colb.Label.Rotation = 0;
    subplot(2,4,8),
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

    Zsnorm = Zf1{4}(:,:,a).*IndX(:,:,a);
    Zsnorm = round(254* (Zsnorm-min(Zsnorm(:)))/(max(Zsnorm(:))-min(Zsnorm(:))))+1;
    Zsnorm(isnan(Zsnorm)) = 1;

    colors = flipud(parula(255));

    ColR = Zsnorm*0; ColG = ColR; ColB = ColR;

    ColR(:) = colors(Zsnorm,1);
    ColG(:) = colors(Zsnorm,2);
    ColB(:) = colors(Zsnorm,3);

    Col = cat(3,ColR,ColG,ColB);

    gs = mesh(Yf1{4}(1:aa:end,1:aa:end,a).*IndX(1:aa:end,1:aa:end,a), ...
        Zf1{4}(1:aa:end,1:aa:end,a),...
        Xf1{4}(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:).*IndX(1:aa:end,1:aa:end,a));
    hold on,

    Col = cat(3, 0*ColR+0.3, 0*ColG+0.3, 0*ColB+0.3);
    sombra = mesh(Yf1{4}(1:aa:end,1:aa:end,a).*IndX(1:aa:end,1:aa:end,a), ...
        Zf1{4}(1:aa:end,1:aa:end,a),...
        0*Xf1{4}(1:aa:end,1:aa:end,a)+limsz,Col(1:aa:end,1:aa:end,:));
    %     sombra.CDataSource = 0*Yh2f(1:aa:end,1:aa:end,a)+120;


    xlabel('Y [mm]'), ylabel('Z [mm]'), zlabel('X [mm]')
    %     xlabel(''), ylabel(''), zlabel('')
    gs.Parent.Title.String = ['3D Position Pose-',num2str(pose)];    axis equal
    gs.Parent.Title.FontSize = 16;

%     gs.Parent.Title.Position(2) = gs.Parent.Title.Position(2)*0.8;

    xlim([-130 130])
    zlim([-150 limsz])
    ylim([-100 850])
    %     gs.Parent.Title.String = {'3D Position'};

    %     [xcub,ycub] = meshgrid(-200:400:200,-200:400:200);
    %     gcub = surf(xcub,xcub*0+500,ycub);
    %     gcub.FaceColor = 'r';
    %     gcub.FaceAlpha = 0.3;


    [xsph,ysph,zsph] = sphere(30);

    xsph = Radius_f1(a,4)*xsph+Centers_h1(a,1,4);
    ysph = Radius_f1(a,4)*ysph+Centers_h1(a,2,4);
    zsph = Radius_f1(a,4)*zsph+Centers_h1(a,3,4);
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

    if(grabVid)
        saveas(figure(1000),sprintf('PhaseErrorMaps SphereOLEN Stereo - Coef02- pose %d.png',pose),'png')
        frame = imread(sprintf('PhaseErrorMaps SphereOLEN Stereo - Coef02- pose %d.png',pose));
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

if(grabVid)
    close(writerObj);
end














%%
rang =2;
aa = 5;
nrows_fig = 1;
ncols_fig = 4;
aup = 0.03;
colMesh = turbo(255);


figex = figure(1000);

figex.Position = [ -72         858        1395         889];

grabar =1;

if(grabar)    
    writerObj = VideoWriter('Sphere-OLEN','MPEG-4');
    writerObj.FrameRate = 1;
    open(writerObj);
end

for pose  =  1:7
    a = order(pose);
 
    subplot(2,3,1),
    %     gg = mesh(znor);

    gg = imagesc(e_s(:,:,a)');
    gg.Parent.Color = 'none';
    %     gg.Parent.FontSize = 11;
    axis equal, 
    
    st =  regionprops(IndX(:,:,a)>0, 'BoundingBox' );
    st = st.BoundingBox;


    ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar



    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'Stereo'};
    colormap(colMesh)
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';
   

    subplot(2,3,2),
%     figure(902)
    gg = imagesc(e_h1{4}(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal, 
    
    ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar
    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'POL6-V'};
    colormap(colMesh)
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';



    subplot(2,3,3),
    gg = imagesc(e_h2{1}(:,:,a)');
    gg.Parent.Color = 'none';
    gg.Parent.FontSize = 11;
    axis equal,     ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar

    ylabel('$u_c$ [px]','Interpreter','latex')
    xlabel('$v_c$ [px]','Interpreter','latex')
    gg.Parent.Title.String = {'Error map';'POL3-E'};
    colormap(colMesh)
    %     colorbar
    caxis([-rang rang+0.002])
    gg.Parent.FontSize = 15;
    gg.Parent.FontWeight = 'bold';


%     figure(9021)
%     gg = imagesc(e_h2{4}(:,:,a)');
%     gg.Parent.Color = 'none';
%     gg.Parent.FontSize = 11;
%     axis equal, 
%     ylim([st(1) st(1)+st(3)]), xlim([st(2) st(2)+st(4)]), %colorbar
%     ylabel('$u_c$ [px]','Interpreter','latex')
%     xlabel('$v_c$ [px]','Interpreter','latex')
%     gg.Parent.Title.String = {'Error map';'POL6-E'};
%     colormap(colMesh)
%     %     colorbar
%     caxis([-rang rang+0.002])
%     gg.Parent.FontSize = 15;
%     gg.Parent.FontWeight = 'bold';



    subplot(2,3,4),
    hold off

    g2 = histogram(e_s(:,:,a)   ,(-rang:0.01:rang),'DisplayName', ...
        ['Stereo.', ' Rmse :', sprintf('%3.3f',erms_s(a))]); hold on
        g3 = histogram(e_h1{4}(:,:,a)  ,(-rang:0.01:rang),'DisplayName', ...
        ['POL6-V.', ' Rmse :', sprintf('%3.3f',erms_f1(a,4))]);
    
    g4 = histogram(e_h2{1}(:,:,a) ,(-rang:0.01:rang),'DisplayName', ...
        ['POL3-E.', ' Rmse :', sprintf('%3.3f',erms_f2(a,1))]);

   

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

%     g5.FaceColor = [0.8 0 0.8];
%     g5.EdgeColor = 'none';
%     g5.FaceAlpha =0.6;
%     g5.LineStyle = 'none';
%     g5.Orientation = 'vertical';


    g2.Parent.YLim = [0 10*10^4];
    g2.Parent.XLim = [-rang rang*1.005];
    g2.Parent.XLabel.String = 'Error [mm]';
    g2.Parent.YLabel.String = 'Points';
    g2.Parent.FontSize = 16;
    g2.Parent.XLabel.FontSize = 16;
    g2.Parent.Title.String = 'Error Histograms';
    g2.Parent.Title.Position(2) = g2.Parent.Title.Position(2)*1.05;

    %     g.XAxis
    leg = legend('FontSize',9,'Location','best');
    leg.Orientation = 'vertical';
    leg.FontSize = 12;


    colormap(turbo(256))
    colb = colorbar();
    colb.Position = [0.0600    0.4000    0.0164    0.3226];
    colb.Ticks = linspace(0,1,5);
    colb.TickLabels = {'-2';'-1';'0';'1';'2'};



    ffcb = subplot(2,3,5),
    hold off


    x1 = e_h1{4}(:,:,a)+Radius_f1(a,4);
    x1 = x1(~isnan(x1));

    x2 = e_s(:,:,a)+Radius_s(a);
    x2 = x2(~isnan(x2));

    x3 = e_h2{1}(:,:,a)+Radius_f2(a,1);
    x3 = x3(~isnan(x3));

    boxplot([x2,x1,x3],'Notch','on','OutlierSize',1,'Labels',{'Stereo','POL6-V','POL3-E'});
    ffcb.YLabel.String = 'Radius [mm]';
    ffcb.FontSize = 16;
    ffcb.XLabel.FontSize = 16;
    ffcb.Title.String = 'Estimated Radius';
    ffcb.Position = [0.5227/1.25    0.1051*1.1    2*0.1012    0.3173];
%     ffcb.Title.Position(2) = 1.1*ffcb.Title.Position(2);

%     ylim([90 100])
    hold on
    plot(0:3, [98 98 98 98],'--r','LineWidth',1.5)
    legend('Reference Radius','Location','best')

    grid on

%     plot()
%     ff1 = figure(904);
    subplot(2,3,6)
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

    Zsnorm = Zf1{4}(:,:,a).*IndX(:,:,a);
    Zsnorm = round(254* (Zsnorm-min(Zsnorm(:)))/(max(Zsnorm(:))-min(Zsnorm(:))))+1;
    Zsnorm(isnan(Zsnorm)) = 1;

    colors = flipud(parula(255));

    ColR = Zsnorm*0; ColG = ColR; ColB = ColR;

    ColR(:) = colors(Zsnorm,1);
    ColG(:) = colors(Zsnorm,2);
    ColB(:) = colors(Zsnorm,3);

    Col = cat(3,ColR,ColG,ColB);

    gs = mesh(Yf1{4}(1:aa:end,1:aa:end,a).*IndX(1:aa:end,1:aa:end,a), ...
        Zf1{4}(1:aa:end,1:aa:end,a),...
        Xf1{4}(1:aa:end,1:aa:end,a),Col(1:aa:end,1:aa:end,:).*IndX(1:aa:end,1:aa:end,a));
    hold on,

    Col = cat(3, 0*ColR+0.3, 0*ColG+0.3, 0*ColB+0.3);
    sombra = mesh(Yf1{4}(1:aa:end,1:aa:end,a).*IndX(1:aa:end,1:aa:end,a), ...
        Zf1{4}(1:aa:end,1:aa:end,a),...
        0*Xf1{4}(1:aa:end,1:aa:end,a)+limsz,Col(1:aa:end,1:aa:end,:));
    %     sombra.CDataSource = 0*Yh2f(1:aa:end,1:aa:end,a)+120;


    xlabel('Y [mm]'), ylabel('Z [mm]'), zlabel('X [mm]')
    %     xlabel(''), ylabel(''), zlabel('')
    gs.Parent.Title.String = ['3D Position Pose-',num2str(pose)];    axis equal
    gs.Parent.Title.FontSize = 16;

%     gs.Parent.Title.Position(2) = gs.Parent.Title.Position(2)*0.8;

    xlim([-130 130])
    zlim([-150 limsz])
    ylim([-100 850])
    %     gs.Parent.Title.String = {'3D Position'};

    %     [xcub,ycub] = meshgrid(-200:400:200,-200:400:200);
    %     gcub = surf(xcub,xcub*0+500,ycub);
    %     gcub.FaceColor = 'r';
    %     gcub.FaceAlpha = 0.3;


    [xsph,ysph,zsph] = sphere(30);

    xsph = Radius_f1(a,4)*xsph+Centers_h1(a,1,4);
    ysph = Radius_f1(a,4)*ysph+Centers_h1(a,2,4);
    zsph = Radius_f1(a,4)*zsph+Centers_h1(a,3,4);
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
        saveas(figure(1000),sprintf('PhaseErrorMaps SphereOLEN Stereo - Coef02- pose %d.png',pose),'png')
        frame = imread(sprintf('PhaseErrorMaps SphereOLEN Stereo - Coef02- pose %d.png',pose));
        writeVideo(writerObj, frame);
    end

end

if(grabar)
    close(writerObj);
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
%%

a = 5;

figure, mesh(Xh1(:,:,a),Yh1(:,:,a),Zh1(:,:,a))



