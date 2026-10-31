

pathExp   = '23-03-07 - Pruebas';
pathR3D = 'Zeus1';

load(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_PhasesData.mat'],'Fx','Fy','MaskC','images','qFy')
% MaskC = Mask;



Indi = NaN*MaskC; Indi((qFy>0.35)&(images>60)) = 1;

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
HybridModelname = 'hybrid6_5_Vr';
HybridModel2 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
[Xh2,Yh2,Zh2] = HybridReconstruction(Fy.*Indi,1,HybridModel2);

%%
HybridModelname = 'hybrid3_2_Fa';
HybridModel3 = load(['..\Data\',pathExp,'\',pathSteCalib,'\',StereoCalibNom,'_',HybridModelname,'.mat']);
[Xh3,Yh3,Zh3] = HybridReconstruction(Fy.*Indi,1,HybridModel3);

%%



[PCs  ,NewMasks]   = XYZtoPC(Xs  ,Ys  ,Zs  ,images,Indi);
[PCh2 ,NewMaskh2]  = XYZtoPC(Xh2 ,Yh2 ,Zh2 ,images,Indi);
[PCh2f,NewMaskh2f] = XYZtoPC(Xh3,Yh3,Zh3,images,Indi);

%%
for i =1:numel(PCs)

    pcwrite(PCs{i}  ,['Zeus_Stereo_pose',num2str(i),'.ply'])
    pcwrite(PCh2{i} ,['Zeus_POL6-V_pose',num2str(i),'.ply'])
    pcwrite(PCh2f{i},['Zeus_POL3-E_pose',num2str(i),'.ply'])

end
%%

pc1 = PCh2f{1};
pc2 = PCh2f{2};
pc3 = PCh2f{3};

Xp1 = cat(3,Xh2f(:,:,1),Yh2f(:,:,1),Zh2f(:,:,1),images(:,:,1),Indi(:,:,1));
Xp2 = cat(3,Xh2f(:,:,2),Yh2f(:,:,2),Zh2f(:,:,2),images(:,:,2),Indi(:,:,2));
Xp3 = cat(3,Xh2f(:,:,3),Yh2f(:,:,3),Zh2f(:,:,3),images(:,:,3),Indi(:,:,3));

[PC_h2f_1,Xp1_t] = Sift3DRegister(Xp3,Xp1);
[PC_h2f_3,Xp3_t] = Sift3DRegister(Xp3,Xp2);



%%
percentage1 = 0.5;
percentage2 = 0.7;
percentage3 = 0.9;

pcwrite(pcdownsample(PC_h2f_1,'random',percentage1),['Zeus_h2f_1_',num2str(percentage1),'_reg.ply'] ,'PLYFormat','binary')
pcwrite(pcdownsample(PC_h2f_3,'random',percentage2),['Zeus_h2f_2_',num2str(percentage2),'_reg.ply'] ,'PLYFormat','binary')
pcwrite(pcdownsample(PCh2f{3},'random',percentage3),['Zeus_h2f_3_',num2str(percentage3),'_reg.ply'] ,'PLYFormat','binary')
%%


pcwrite(PC_h2f_1,'Zeus_h2f_1_reg.ply' ,'PLYFormat','binary')
pcwrite(PCh2f{3}  ,'Zeus_h2f_3_reg.ply' ,'PLYFormat','binary')
pcwrite(PC_h2f_3,'Zeus_h2f_5_reg.ply' ,'PLYFormat','binary')


%%




PC1 = PCh2f{1}.Location(:,[2 3 1]); 
PC1(:,3) = PC1(:,3);  PC1(:,1) = -PC1(:,1);
PC1 = pointCloud(PC1);  PC1.Color = PCh2f{1}.Color;
PC1 = pcdenoise(PC1,'Threshold',4,'NumNeighbors',8);


PC2 = PCh2f{2}.Location(:,[2 3 1]);  
PC2(:,3) = PC2(:,3);  PC2(:,1) = -PC2(:,1);
PC2 = pointCloud(PC2);  PC2.Color = PCh2f{2}.Color;
PC2 = pcdenoise(PC2,'Threshold',4,'NumNeighbors',8);


PC3 = PCh2f{3}.Location(:,[2 3 1]);  
PC3(:,3) = PC3(:,3);  PC3(:,1) = -PC3(:,1);
PC3 = pointCloud(PC3);  PC3.Color =PCh2f{3}.Color;
PC3 = pcdenoise(PC3,'Threshold',4,'NumNeighbors',8);

aux = PC2;
PC2 = PC3; PC3 = aux;

PC4 = PC_h2f_1.Location(:,[2 3 1]);  
PC4(:,3) = PC4(:,3);  PC4(:,1) = -PC4(:,1);
PC4 = pointCloud(PC4);  PC4.Color = PC_h2f_1.Color;
PC4 = pcdenoise(PC4,'Threshold',4,'NumNeighbors',8);

PC5 = PC_h2f_3.Location(:,[2 3 1]);  
PC5(:,3) = PC5(:,3);  PC5(:,1) = -PC5(:,1);
PC5 = pointCloud(PC5);  PC5.Color =PC_h2f_3.Color;
PC5 = pcdenoise(PC5,'Threshold',4,'NumNeighbors',8);

%%

nrows_fig = 2;
ncols_fig = 3;
vv = [35 20];

figPri = figure(905); 

% subplot(nrows_fig,ncols_fig,1)
g1 = pcshow(PC1);

g1.Color = [1 1 1];
g1.Parent.Color = [1 1 1];
g1.XAxis.Color = [0 0 0];
g1.YAxis.Color = [0 0 0];
g1.ZAxis.Color = [0 0 0];
g1.ZLim = [-160 160];
g1.XLim = [-120 120];
g1.YLim = min(g1.YLim)+[0 200];

g1.View = vv;
g1.ZDir = 'reverse';
% g1.XDir = 'reverse';

% subplot(nrows_fig,ncols_fig,2)
% hold on
figure(902),

g2 = pcshow(PC2);
g2.Color = [1 1 1];
g2.Parent.Color = [1 1 1];
g2.XAxis.Color = [0 0 0];
g2.YAxis.Color = [0 0 0];
g2.ZAxis.Color = [0 0 0];
g2.ZLim = [-160 160];
g2.XLim = [-120 120];
g2.YLim = min(g2.YLim)+[0 200];

g2.View = vv;
g2.ZDir = 'reverse';
% g2.XDir = 'reverse';

% subplot(nrows_fig,ncols_fig,3)
figure(903),

g3 = pcshow(PC3);

g3.Color = [1 1 1];
g3.Parent.Color = [1 1 1];
g3.XAxis.Color = [0 0 0];
g3.YAxis.Color = [0 0 0];
g3.ZAxis.Color = [0 0 0];
g3.ZLim = [-160 160];
g3.XLim = [-120 120];
g3.YLim = min(g3.YLim)+[0 200];
g3.View = vv;
g3.ZDir = 'reverse';
% g3.XDir = 'reverse';


% subplot(nrows_fig,ncols_fig,5)
figure(904),hold off
g4 = pcshowpair(PC2,PC2); 
hold on,

g4.Children(2).Visible = 'off';


g6 = pcshowpair(PC4,PC4); 

g6.Children(1).Visible = 'off';
g6.Children(2).CData = g6.Children(1).CData(:,[1 3 2]);


g5 = pcshowpair(PC5,PC5); 
% pcshow(PC2)
% pcshow(PC5)
g4.Color = [1 1 1];
g4.Parent.Color = [1 1 1];
g4.XAxis.Color = [0 0 0];
g4.YAxis.Color = [0 0 0];
g4.ZAxis.Color = [0 0 0];
g4.ZLim = [-160 160];
g4.XLim = [-120 120];
g4.YLim = g2.YLim;
g4.View = vv;
g4.ZDir = 'reverse';
% g4.XGrid = 'off'; g4.XAxis
% g4.YGrid = 'off';
% g4.ZGrid = 'off';

g1.XLabel.String = 'X [mm]'; g1.YLabel.String = 'Z [mm]'; g1.ZLabel.String = 'Y [mm]'; 
g2.XLabel.String = 'X [mm]'; g2.YLabel.String = 'Z [mm]'; g2.ZLabel.String = 'Y [mm]'; 
g3.XLabel.String = 'X [mm]'; g3.YLabel.String = 'Z [mm]'; g3.ZLabel.String = 'Y [mm]'; 
g5.XLabel.String = 'X [mm]'; g5.YLabel.String = 'Z [mm]'; g5.ZLabel.String = 'Y [mm]'; 

g1.FontSize = 15; g1.LineWidth = 1.5;
g2.FontSize = 15; g2.LineWidth = 1.5;
g3.FontSize = 15; g3.LineWidth = 1.5;
g5.FontSize = 15; g5.LineWidth = 1.5;

g5.Children(1).Visible = 'off';
g5.Children(2).CData = g5.Children(1).CData(:,[2 1 3]);
% g4.Children(1).CData(3,:)

% g4.Children(1).MarkerFaceColor = 'r';

%%
exportgraphics(figure(902),'F1.png','Resolution',600)
exportgraphics(figure(903),'F2.png','Resolution',600)
exportgraphics(figure(904),'F3.png','Resolution',600)
exportgraphics(figure(905),'F4.png','Resolution',600)


%%


figure, 
imagesc(images(:,:,3))
g1 = drawline;

X1 = Xh2f(:,:,3); Y1 = Yh2f(:,:,3); Z1 = Zh2f(:,:,3); 
X2 = Xp1_t(:,:,1); Y2 = Xp1_t(:,:,2); Z2 = Xp1_t(:,:,3); 
X3 = Xp3_t(:,:,1); Y3 = Xp3_t(:,:,2); Z3 = Xp3_t(:,:,3); 


M2 = Xp1_t(:,:,4)>0;
M3 = Xp3_t(:,:,4)>0;


F2 = scatteredInterpolant(X2(M2(:)),Y2(M2(:)),Z2(M2(:)));
F3 = scatteredInterpolant(X3(M3(:)),Y3(M3(:)),Z3(M3(:)));

%%
Puntos = g1.Position;
% Puntos = [1355.33870967742	656.476676384839;
%            293.587557603687	656.476676384839];

x1 = Puntos(1,1); x2 = Puntos(2,1);
y1 = Puntos(1,2); y2 = Puntos(2,2);
m = (y2-y1)/(x2-x1);  b = y2-m*x2;
Dx = linspace(x1,x2,200);
Dy = m*Dx + b;

% figure, imagesc(images(:,:,2)), hold on, plot(Dx,Dy)


X1_line = interp2(X1,Dx,Dy);  Y1_line = interp2(Y1,Dx,Dy);  Z1_line = interp2(Z1,Dx,Dy); 

X2_line = X1_line;  Y2_line = Y1_line; 
X3_line = X1_line;  Y3_line = Y1_line; 

Z2_line = F2(X1_line,Y2_line); 
Z3_line = F3(X1_line,Y2_line);


X_t = [X1_line(:); X2_line(:); X3_line(:)];
Y_t = [Y1_line(:); Y2_line(:); Y3_line(:)];
Z_t = [Z1_line(:); Z2_line(:); Z3_line(:)];

[coeff,score1,latent] = pca([X_t(:) Y_t(:) Z_t(:)]);

n1 = numel(X1_line(:)); n2 = numel(X2_line(:)); n3 = numel(X3_line(:)); 

X_P1 = score1(1:n1,1);
X_P2 = score1(n1+(1:n2),1);
X_P3 = score1(n1+n2+(1:n3),1);

Y_P1 = score1(1:n1,2);
Y_P2 = score1(n1+(1:n2),2);
Y_P3 = score1(n1+n2+(1:n3),2);

% [X_P1 X_P2 X_P3]

figure(10), hold off
plt3 =plot(X_P3,-Y_P3,'*','LineWidth',2.5); hold on
plt1 =plot(X_P1,-Y_P1,'*g');
plt2 =plot(X_P2,-Y_P2,'*b');

axis equal


plt1.Marker = '.'; plt1.MarkerSize = 12; plt1.Color = [89 254 90]/255;
plt2.Marker = '.'; plt2.MarkerSize = 10; plt2.Color = [127 169 206]/255;
plt3.Marker = '.'; plt3.MarkerSize = 20; plt3.Color = [255 142 142]/255;
plt1.Parent.Color = [0 0 0];
% plt3.Color = [255 142 142]/255;

%%
aa = 5;



figure(80), hold on, 


pos = 1;
mesh(-Yh2f(1:aa:end,1:aa:end,pos).*Indi(1:aa:end,1:aa:end,pos), ...
              Zh2f(1:aa:end,1:aa:end,pos), ...
             -Xh2f(1:aa:end,1:aa:end,pos), ...
             images(1:aa:end,1:aa:end,pos))

pos = 3;
mesh(-Yh2f(1:aa:end,1:aa:end,pos).*Indi(1:aa:end,1:aa:end,pos), ...
              Zh2f(1:aa:end,1:aa:end,pos), ...
             -Xh2f(1:aa:end,1:aa:end,pos), ...
             images(1:aa:end,1:aa:end,pos))

pos = 5;
mesh(-Yh2f(1:aa:end,1:aa:end,pos).*Indi(1:aa:end,1:aa:end,pos), ...
              Zh2f(1:aa:end,1:aa:end,pos), ...
             -Xh2f(1:aa:end,1:aa:end,pos), ...
             images(1:aa:end,1:aa:end,pos))





colormap gray
axis equal

%%

