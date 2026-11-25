pathh = 'D:\OneDrive - Universidad Tecnológica de Bolívar\PC HP\Documentos\DOCTORADO\PasantiaPurdue_Experiments\FringeGeneration\PatronesLC4500\P18S18Nbit7\PatternToCalibrate\';
poses = 50;
for k=1:poses
        i = k-1;
        if(i<10), aux2 = ['0',num2str(i)]; else, aux2 = num2str(i); end
        if(k<10), aux = ['0',num2str(k)]; else, aux = num2str(k); end
       
        movefile([pathh,'f_',aux,'.bmp'],[pathh,'f_',aux2,'.bmp']);
end
