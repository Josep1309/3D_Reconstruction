


direC = 'D:\OneDrive - Universidad Tecnológica de Bolívar\PC HP\Documentos\DOCTORADO\PasantiaPurdue_Experiments\Data\23-02-25 - Pruebas\Mirror\';

nomb = 'Mirror_R3D-poses19-28.mat';



load([direC,nomb]);

%%
index = 19:28;
for a = 1:numel(index)


Ind = e_h1(:,:,a)*0+1;
Ind(isnan(Ind)) = NaN;

X = Xh1(:,:,a).*Ind; 
Y = Yh1(:,:,a).*Ind; 
Z = Zh1(:,:,a); 
CC = uint8(((e_h1(:,:,a) + 1)/2)*255)+1;
 

colores = 255*jet(256);

Cols = [colores(CC(~isnan(X(:))),1),colores(CC(~isnan(X(:))),2),colores(CC(~isnan(X(:))),3)];



M =[];
M(:,1) = X(~isnan(X(:))); M(:,2) =Y(~isnan(X(:))); M(:,3) = Z(~isnan(X(:)));


nubep=pointCloud(M);

nubep.Color = uint8(Cols);
%         nubep.Color = uint8(cod255(find(mask(1:a:end))));
%I_objeto(:,:,toma) = Io;
pcwrite(nubep,['Mirror_Pose_H1_',num2str(index(a)),'.ply'],'PLYFormat','binary')

end

%%
for a = 1:numel(index)


Ind = e_h1v(:,:,a)*0+1;
Ind(isnan(Ind)) = NaN;

X = Xh1v(:,:,a).*Ind; 
Y = Yh1v(:,:,a).*Ind; 
Z = Zh1v(:,:,a); 
CC = uint8(((e_h1v(:,:,a) + 1)/2)*255)+1;
 

colores = 255*jet(256);

Cols = [colores(CC(~isnan(X(:))),1),colores(CC(~isnan(X(:))),2),colores(CC(~isnan(X(:))),3)];



M =[];
M(:,1) = X(~isnan(X(:))); M(:,2) =Y(~isnan(X(:))); M(:,3) = Z(~isnan(X(:)));


nubep=pointCloud(M);

nubep.Color = uint8(Cols);
%         nubep.Color = uint8(cod255(find(mask(1:a:end))));
%I_objeto(:,:,toma) = Io;
pcwrite(nubep,['Mirror_Pose_H1v_',num2str(index(a)),'.ply'],'PLYFormat','binary')

end


%%
for a = 1:numel(index)


Ind = e_s(:,:,a)*0+1;
Ind(isnan(Ind)) = NaN;

X = Xs(:,:,a).*Ind; 
Y = Ys(:,:,a).*Ind; 
Z = Zs(:,:,a); 
CC = uint8(((e_s(:,:,a) + 1)/2)*255)+1;
 

colores = 255*jet(256);

Cols = [colores(CC(~isnan(X(:))),1),colores(CC(~isnan(X(:))),2),colores(CC(~isnan(X(:))),3)];



M =[];
M(:,1) = X(~isnan(X(:))); M(:,2) =Y(~isnan(X(:))); M(:,3) = Z(~isnan(X(:)));


nubep=pointCloud(M);

nubep.Color = uint8(Cols);
%         nubep.Color = uint8(cod255(find(mask(1:a:end))));
%I_objeto(:,:,toma) = Io;
pcwrite(nubep,['Mirror_Pose_St_',num2str(index(a)),'.ply'],'PLYFormat','binary')

end




