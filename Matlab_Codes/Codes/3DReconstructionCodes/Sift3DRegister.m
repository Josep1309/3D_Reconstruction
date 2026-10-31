function [PC_trans,Xp2_t,tformEst,rmse] = Sift3DRegister(Xp1,Xp2)
%%
% Permite registrar dos reconstrucciones 3D por medio la deteccion de
% puntos caracteristicos en la imagen
% Esta funcion devuelve Xp2 transformada de tal forma que esté alineada a
% la reconstruccion 1
% Xp1: Matriz de mxnx5 no movil
% Xp2: Matriz de mxnx5



I1 = uint8(Xp1(:,:,4));
I2 = uint8(Xp2(:,:,4));

X1 = Xp1(:,:,1); X2 = Xp2(:,:,1); 
Y1 = Xp1(:,:,2); Y2 = Xp2(:,:,2); 
Z1 = Xp1(:,:,3); Z2 = Xp2(:,:,3); 

mask1 = Xp1(:,:,5)>0; 
mask2 = Xp2(:,:,5)>0; 

points1 = detectSIFTFeatures(I1,"EdgeThreshold",50,"NumLayersInOctave",1,"Sigma",1);
% figure, imshow(I1,[]), hold on
% plot(points1.Location(:,1),points1.Location(:,2),'*')

points2 = detectSIFTFeatures(I2,"EdgeThreshold",50,"NumLayersInOctave",1,"Sigma",1);
% figure, imshow(uint8(I2),[]), hold on
% plot(points2.Location(:,1),points2.Location(:,2),'*')


[f1,vpts1] = extractFeatures(I1,points1);
[f2,vpts2] = extractFeatures(I2,points2);


indexPairs = matchFeatures(f1,f2) ;

matchedPoints1 = vpts1(indexPairs(:,1));
matchedPoints2 = vpts2(indexPairs(:,2));


f1match = matchedPoints1.Location';
f2match = matchedPoints2.Location';

% show the match
figure, imshow([I1,I2],[]);
o = size(I1,2);
line([f1match(1,:);f2match(1,:)+o], ...
[f1match(2,:);f2match(2,:)]) ;
for ln=1:size(f1match,2)
x = f1match(1,ln);
y = f1match(2,ln);
text(x,y,sprintf('%d',ln), 'Color', 'r');
end

for ln=1:size(f2match,2)
x = f2match(1,ln);
y = f2match(2,ln);
text(x+o,y,sprintf('%d',ln), 'Color', 'r');
end
figure; showMatchedFeatures(I1,I2,matchedPoints1,matchedPoints2);
legend('matched points 1','matched points 2');



X1_m = interp2(X1,f1match(1,:),f1match(2,:));
Y1_m = interp2(Y1,f1match(1,:),f1match(2,:));
Z1_m = interp2(Z1,f1match(1,:),f1match(2,:));


X2_m = interp2(X2,f2match(1,:),f2match(2,:));
Y2_m = interp2(Y2,f2match(1,:),f2match(2,:));
Z2_m = interp2(Z2,f2match(1,:),f2match(2,:));



PointsM1 = [X1_m' Y1_m' Z1_m'];
PointsM2 = [X2_m' Y2_m' Z2_m'];

index = (sum(isnan(PointsM2),2)+sum(isnan(PointsM1),2))<1;

[tformEst,inlierIndex] = estimateGeometricTransform3D(PointsM2(index,:), PointsM1(index,:),'rigid','MaxDistance',0.3); 


[PC1, mask1] = XYZtoPC(X1,Y1,Z1,I1,mask1);
[PC2, mask2] = XYZtoPC(X2,Y2,Z2,I2,mask2);


% [tformEst,~,rmse] = pcregisterndt(pcdownsample(PC2,"random",0.1), ...
%                            pcdownsample(PC1,"random",0.6), ...
%                            2, InitialTransform = tformEst);
PC2_ds = pcdownsample(PC2,"random",0.01);
[tformEst,~,rmse] = pcregistericp(PC2_ds, ...
                           PC1, ...
                           "Metric","pointToPlane","InitialTransform",tformEst);
PC2_ds.Count 
rmse
% pcregisterndt
% pcregistericp
PC_trans = pctransform(PC2,tformEst);
% PC_trans.Color =  repmat(uint8([255 250 0]),[ size(PC_trans.Color,1) 1]);

figure, pcshow(PC_trans), hold on , pcshow(PC1)

X_tras = X2; Y_tras = Y2; Z_tras = Z2; 

X_tras(mask2) = PC_trans.Location(:,1);
Y_tras(mask2) = PC_trans.Location(:,2);
Z_tras(mask2) = PC_trans.Location(:,3);

Xp2_t = cat(3,X_tras,Y_tras,Z_tras,mask2);


end

