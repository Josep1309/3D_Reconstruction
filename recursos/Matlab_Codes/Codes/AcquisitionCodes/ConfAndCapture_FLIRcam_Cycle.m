%%
imaqreset
vid = videoinput('gentl', 1, 'Mono8');
src = getselectedsource(vid);
% vid.FramesPerTrigger = 10;

% Configurar la visualización
figP = figure(2);
h = gca; 
imshow(zeros(1936,1464));
hImage=image(zeros(1936,1464,1),'Parent',figP.Children);
preview(vid,hImage);
axis equal;
camroll(-90)
xlim([0 1936])
src.GainAuto = 'off';
src.TriggerMode = 'On';
src.TriggerSource = 'Line0'; 
src.TriggerDelay = 20;
src.ExposureMode = 'TriggerWidth';
%% Acquisition

Dire = 'D:\OneDrive - Universidad Tecnológica de Bolívar\PC HP\Documentos\DOCTORADO\PasantiaPurdue_Experiments\Data\23-02-07 - Pruebas\';
carp = 'Estereo3\';
nFrames = 50;

NI =0; 
i=1;
if NI==0,bandera=NI;NI=1;else,bandera=1;end % Se inicializan las variables
while (i<=NI)
    pose = sprintf('%02d',i-1);

    % Se va avisando el numero de toma que se está capturando
    hp=warndlg(['Imagen: ',num2str(i)],'CALIBRACION CORRESPONDENCIA');
    if(~bandera)
        waitfor(hp);
    end

    Frames(:,:,:,i) = GetCamFrames(vid,nFrames);

    col = shiftdim(sum(double(Frames(:,:,:,i)),[1 2]));
    [~,PointN] = max(diff(col));
    RefPoints(:,i) = PointN;


%     savePatterns([Dire, carp, 'pose_', pose,'\'],'P18_F', Frames_aux, PointN+1,secN)
%     fprintf('\n Imagenes guardadas \n')

    if (bandera==0) % ¿El usuario desconoce cuantas tomas quiere realizar?
        choice = questdlg('Desea capturar otra imagen?','Dessert Menu','Yes','No','No');
        if strcmp(choice,'No'),i=NI+1;else,i=i+1;NI=i;end
    else % El usuario quiere capturar un numero fijo de tomas
        i=i+1;
        close(hp)
    end
    %if(handles.checkr || handles.checkd),close(hp);end
end

hp=warndlg('Imagenes tomadas...');
waitfor(hp);

%%

Dire = 'D:\OneDrive - Universidad Tecnológica de Bolívar\PC HP\Documentos\DOCTORADO\PasantiaPurdue_Experiments\Data\23-02-19 - Pruebas\';
carp = 'WhiteBoard\';
secN = [24 24 2];

for i = 1
    pose = sprintf('%02d',i-1);
    savePatterns([Dire, carp, 'pose_', pose,'\'],'P18_F', Frames(:,:,:,i), RefPoints(i)+1,secN)
    fprintf('\n Imagenes guardadas %d \n',i)
end



%%
[~,PointN] = max(diff(col));

for i = 1:50
    figure(90), imagesc(imags(:,:,i)), colormap gray
    pause()
end

