carp = 'D:\OneDrive - Universidad Tecnológica de Bolívar\PC HP\Documentos\DOCTORADO\PasantiaPurdue_Experiments\Data\23-01-20 - Pruebas\Estereo\';

pitch = 18;
poses = 13;
nimages = 25;

for i=0:poses
    if(i<10), aux2 = ['0',num2str(i)]; else aux2 = num2str(i); end
    for j = 0:nimages
        if(j<10), aux = ['0',num2str(j)]; else aux = num2str(j); end
        np = [carp,'pose_',aux2,'\V\'];
        mkdir(np)
        movefile([np(1:end-2),'V_P',num2str(pitch),'_F',aux,'.png'],[np,'P',num2str(pitch),'_F',aux,'.png']);

        np = [carp,'pose_',aux2,'\H\'];
        mkdir(np)
        movefile([np(1:end-2),'H_P',num2str(pitch),'_F',aux,'.png'],[np,'P',num2str(pitch),'_F',aux,'.png']);
    end

end



