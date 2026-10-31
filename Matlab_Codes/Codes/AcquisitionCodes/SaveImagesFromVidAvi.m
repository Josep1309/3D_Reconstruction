
nomCarpb{1} = 'Patron\';
nomCarpb{2} = 'Plano\';
nomCarpb{3} = 'Objeto\';
% nomCarpb{4} = 'Zeus\';

for j = 1:4

    nomCarp = nomCarpb{j};
DirVid = ['C:\Users\raula\OneDrive\Desktop\Pruebas-24-05-14\' nomCarp];


Dire = 'D:\OneDrive - Universidad Tecnológica de Bolívar\PC HP\Documentos\UTB\DOCTORADO\PasantiaPurdue_Experiments\Data\Pruebas-24-05-14\';
carp = nomCarp;
secN = [24 24 2];

arch = dir([DirVid '*.avi']);

for i = 1:numel(arch)

    pose = sprintf('%02d',i-1);

    V1 = VideoReader([DirVid,arch(i).name]);

    images = read(V1,[1 Inf]);
    
    Frames = squeeze(images(:,:,1,:));
    col = shiftdim(sum(double(Frames),[1 2]));
    [~,PointN] = max(diff([col; col(1)]));


    
    if(PointN==50)
        PointN=0;
    end

    savePatterns([Dire, carp, 'pose_', pose,'\'],'P18_F', Frames, PointN+1,secN)
    fprintf('\n Imagenes guardadas %d \n',i)
end

end
