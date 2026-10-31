%% Phases Lectures

pathExp   = '23-03-22 - Pruebas';
pathR3D = 'Estereo';

load(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_PhasesData_virtual.mat'],'Fx','Fy','Mask','images')
MaskC = Mask;
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


pathExp   = '23-03-22 - Pruebas';
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
%% R3D Hybrid Virtual


pathExp   = '23-03-22 - Pruebas';
pathSteCalib = 'Estereo';
StereoCalibNom = 'Estereo_TSC_0_2';

resC =  1550;
resR =  1150;
offC = (size(Xs,2) - resC)/2;
offR = (size(Xs,1) - resR)/2;

d1 = Mask; d1(offR+(1:resR),offC+(1:resC)) = 1;
IndX = d1;
ite = 0;

rang = 425:25:825;
for gr = 2:5
    ite = ite+1;
    HybridModelname = ['HybPol',num2str(gr),'_Virt_520-720-9'];
    HybridModel1 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
    Ind2 = NaN.*HybridModel1.N3; Ind2(HybridModel1.N3>10)=1;
    Ind2 = Indi.*Ind2;

    [Xh1,Yh1,Zh1] = HybridReconstruction(Fy.*Indi,1,HybridModel1);
    Xh{ite} = Xh1;
    Yh{ite} = Yh1;
    Zh{ite} = Zh1;

    [e_h1 ,erms_h1 ]  = Plane_fitting(Xh1  .*IndX,Yh1 ,Zh1 ,[],801);
    
    erms_h{ite} = erms_h1;
    e_h{ite} = e_h1;
%     figure(500),
%     plot(Virtual_rec(1:2:end,1),Virtual_rec(1:2:end,i+1),'-*','Linewidth',1.5), hold on,

end

grid on
xlabel(' Z distance [rad]'), 
ylabel(' Error [mm]')
%%
ite = 0;
rang = 425:25:825;
figure(815)
for gr = 2:5
    ite = ite+1;
    plot(rang(1:2:end),erms_h{ite}(1:2:end),'-*','Linewidth',1.5), hold on,
end


pgon = polyshape([520 720 720 520],[0 0 0.25 0.25]);
ypol = plot(pgon);
ypol.EdgeAlpha = 0;
ypol.FaceAlpha = 0.1;

legend('POL2','POL3','POL4','POL5')

grid on
xlabel(' Z distance [rad]'), 
ylabel(' Error [mm]')
ylim([0 0.25])
%% Incidence

l1 = 520; l2 = 720;

Zaux = Zs.*IndX;
nn = shiftdim(sum((~isnan(Zaux.*IndX)),[1 2]));


cp1 = 100*shiftdim(sum((Zaux<l1),[1 2]))./nn;
cp2 = 100*shiftdim(sum((Zaux>l1).*(Zaux<l2),[1 2]))./nn;
cp3 = 100*shiftdim(sum((Zaux>l2),[1 2]))./nn;



[cp1 cp2 cp3]


%% Compare the error maps
index = 1:size(Fy,3);
for a = 4
% a = 4; 
figure(904), 
subplot(1,2,1)
imagesc([e_h{1}(:,:,a) e_h{2}(:,:,a); [e_h{3}(:,:,a) e_h{4}(:,:,a)]]), caxis([-1 1])

 g=gca();
 g.FontSize = 14;
axis equal
ylim([0 2*1200])
title(['Pose ',num2str(index(a))])


rang = 1;
subplot(1,2,2), hold off

            g2 = histogram(e_h{1}(:,:,a)   ,-rang:0.0005:rang); hold on
            g3 = histogram(e_h{2}(:,:,a) ,-rang:0.0005:rang);
            g4 = histogram(e_h{4}(:,:,a)  ,-rang:0.0005:rang);
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

legend('Pol3','Pol4','Pol5')
drawnow

% pause()
% saveas(figure(904),sprintf('PhaseErrorMaps Mirror - pose 07-03 Ste-03Coef %d.png',index(a)),'png')
end
%%

a = 5;

figure, mesh(Xh1(:,:,a),Yh1(:,:,a),Zh1(:,:,a))



