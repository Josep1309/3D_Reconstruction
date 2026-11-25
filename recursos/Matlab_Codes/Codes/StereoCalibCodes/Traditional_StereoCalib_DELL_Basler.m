clear all

addpath PhaseRecoveryCodes

Direc = ['D:\OneDrive - Universidad Tecnológica de Bolívar\PC HP\Documentos\DOCTORADO\PasantiaPurdue_Experiments\Data\23-01-20 - Pruebas\'];
carp = 'Estereo\';


% FringePitch = 20; NStep = 10; NBits = 6;
FringePitch = 18; NStep = 18; NBits = 7; TextureImgNum = 25;
n_poses = 14;


%  Sistema Dell - Basler ac1300 System Info
m_imageWidth = 1280;        %1936   %1280 ;     %2048
m_imageHeight = 1024;       %1464   %1024 ;     %1536
m_projectorWidth =  1280;    %912    %1280;      %912
m_projectorHeight = 800;   %1140   %800;       %1140

% Caracteristica patron
patternSize =   [7, 21];               %[12, 18];         % [7, 21];
centerDistance = 20;                   %15;               % 20;
Pattern_type =   'asymmetric';           %'symmetric';      % asymmetric;
Circ_color =     'white';                %'black';          % white;
 worldPoints = generateCircleGridPoints(patternSize,centerDistance,'PatternType', Pattern_type);

Fx = zeros(m_imageHeight,m_imageWidth,n_poses) ;
Fy = Fx; Mask = Fx; Images = Fx;
M = zeros([patternSize(1)*patternSize(2),2,n_poses,2]);

gammaTh = 0.15;
offset = 40;

figure(81), hold on
g = imagesc(zeros([m_imageHeight m_imageWidth]));
g1 = impoly();
% g2 = plot(0,0); 

for i = 1:n_poses
    
    if(i<11), aux = ['0' num2str(i-1)]; else, aux = num2str(i-1); end

    % Deteccion de puntos - circulos
    % Itex = imread([Direc, carp ,'pose_',aux,'\H\P',num2str(FringePitch),'_F16.png']);
    Itex = imread([Direc, carp ,'pose_',aux,'\H\P',num2str(FringePitch),'_F',num2str(TextureImgNum),'.png']);
    puntos = detectCircleGridPoints(Itex,patternSize,PatternType=Pattern_type,CircleColor=Circ_color);
   
    M(:,:,i,1) = puntos;
    
    MP = reshape( puntos,[patternSize 2 1]);
    
    MaskPoints = createMaskCB(size(Itex),MP,offset);
    % Extraccion de fase
    fileEx = [Direc, carp ,'pose_',aux,'\V\P',num2str(FringePitch),'_F'];
    [Fx_aux, mask_h, texture_h, codeWord, ph] = UnwrapPhaseGrayCode(fileEx, FringePitch, NStep, NBits, [5 5],gammaTh);
    Fx(:,:,i) = Fx_aux;

    fileEx = [Direc, carp ,'pose_',aux,'\H\P',num2str(FringePitch),'_F'];
    [Fy_aux, mask_v, texture_v, codeWord, ph] = UnwrapPhaseGrayCode(fileEx, FringePitch, NStep, NBits, [5 5],gammaTh);
    Fy(:,:,i) = Fy_aux;
    
    % Interpolacion de fase y correspondencia Proyector
    [X,Y] = meshgrid(1:size(Itex,2), 1:size(Itex,1));
    PhasexPoints = interp2(X,Y,Fx_aux,puntos(:,1),puntos(:,2));
    M(:,1,i,2) = PhasexPoints*FringePitch/(2*pi);

    PhaseyPoints = interp2(X,Y,Fy_aux,puntos(:,1),puntos(:,2));
    M(:,2,i,2) = PhaseyPoints*FringePitch/(2*pi);

%     Mask(:,:,i) = imfill(mask_h.*mask_v.*MaskPoints,'hole');
%     Mask(:,:,i) = mask_h.*mask_v;
    Images(:,:,i) =  Itex;

    figure(81), 
    g.CData = Itex;
    title(['Imagen ',num2str(i)])
    hold on

    pause();
    Mask(:,:,i) = g1.createMask;

    figure(80),imagesc(Fx_aux.*Mask(:,:,i)), title('Unwrapped H Phase - GrayCode');
    title(['Imagen ',num2str(i)])
    drawnow
end
%% Fit the phase maps to a phase surface phi(u,v)

% [Fxa ,Fya ,Maskx ,Masky ] = CleanPhase(Fx(:,:,1), Fy(:,:,1),Mask(:,:,1)>0,1);
[Fxa ,Fya ,Maskx ,Masky ] = CleanPhase(Fx, Fy,Mask>0,1); %  5th order 2D-polynomial
Indi = NaN.*Maskx; Indi(Maskx>0) = 1;

% [U,V] = meshgrid(1:1200,1:1024);
% a = -0.1; b = -0.7; c = 400; d = -0.2; e = -0.3;
%  PhasePrueb = (c+d*U+e*V)./(1+a*U+b*V);
%  
% [Ffaf,Ffr ] = Fracfit2D_1(Fx(:,:,1),Mask(:,:,1)>0); % 
% 
[Ffaf,Ffr ] = Fracfit2D_1(Fy,Mask>0); % 


%%
save([Direc,carp,carp(1:end-1),'_PhasesData.mat'],'Fx','Fy','Fxa','Fya','M','Indi','Mask','Images')

disp(" Finalizado ")

%% Estereo Calibration using Matlab Toolbox
NRcoef = 3;
SkewFlag = 0;
 worldPoints = generateCircleGridPoints(patternSize,centerDistance,'PatternType', Pattern_type);
[StereoParams,imagesUsed,estimationErrors] = estimateCameraParameters(M(:,:,1:n_poses,:),worldPoints,'EstimateSkew',logical(SkewFlag),'NumRadialDistortionCoefficients',NRcoef);
figure, showReprojectionErrors(StereoParams);

% [cameraParams,imagesUsed,estimationErrors] = estimateCameraParameters(shiftdim(M(:,:,:,1)),worldPoints);
% [ProjParams,imagesUsed,estimationErrors] = estimateCameraParameters(shiftdim(M(:,:,:,2)),worldPoints);

% Save Data
save([Direc,carp,carp(1:end-1),'_TSC_',num2str(SkewFlag),'_',num2str(NRcoef),'.mat'],'StereoParams')


%% Estereo Calibration by Bouget Toolbox
ve = [1:14];
dire = [Direc,carp];
worldPoints = generateCircleGridPoints(patternSize,centerDistance,'PatternType', Pattern_type);

save_calibraciones(dire,M(:,:,ve,1),double(M(:,:,ve,2)),worldPoints,[[1 1 1 1 1];[1 1 1 1 1]]',[1 1]*0,0)

disp('done')

%%




