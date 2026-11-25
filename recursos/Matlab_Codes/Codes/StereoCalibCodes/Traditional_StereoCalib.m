clear all

fecha = 'Pruebas-24-05-14\';

Direc = ['D:\OneDrive - Universidad Tecnológica de Bolívar\PC HP\Documentos\UTB\DOCTORADO\PasantiaPurdue_Experiments\Data\',fecha];

% Direc = ['C:\Users\OPILAB\Documents\',fecha];
carp = 'Estereo\';


% FringePitch = 20; NStep = 10; NBits = 6;
FringePitch = 18; NStep = 18; NBits = 7; TextureImgNum = 25;
n_poses = 7;


%  Sistema Dell - Basler ac1300 System Info
m_imageWidth = 1024;        %1936   %1280 ;     %2048
m_imageHeight = 800;       %1464   %1024 ;     %1536
m_projectorWidth =  912;    %912    %1280;      %912
m_projectorHeight = 1140;   %1140   %800;       %1140

% Caracteristica patron
patternSize = [8, 21];         % [7, 21]
centerDistance = 16;            % 20
Pattern_type = 'asymmetric';     % asymmetric
Circ_color = 'white';           % white
 worldPoints = generateCircleGridPoints(patternSize,centerDistance,'PatternType', Pattern_type);

Fx = zeros(m_imageHeight,m_imageWidth,n_poses) ;
Fy = Fx; Mask = Fx; MaskP = Fx; Images = Fx;
M = zeros([patternSize(1)*patternSize(2),2,n_poses,2]);

gammaTh = 0.15;
offset = 10;

figure(81), hold off
%g = imagesc(zeros([m_imageHeight m_imageWidth]));
%g1 = drawpolygon();
% g1 = impoly();
% g2 = plot(0,0); 

for i = 1:n_poses
    
    if(i<11), aux = ['0' num2str(i-1)]; else, aux = num2str(i-1); end

    % Deteccion de puntos - circulos
    % Itex = imread([Direc, carp ,'pose_',aux,'\H\P',num2str(FringePitch),'_F16.png']);
    Itex = imread([Direc, carp ,'pose_',aux,'\H\P',num2str(FringePitch),'_F',num2str(TextureImgNum),'.png']);
    puntos = detectCircleGridPoints(Itex,patternSize,PatternType=Pattern_type,CircleColor=Circ_color);
    
    if(i==1)
    g = imagesc(Itex);
    g1 = drawpolygon();
    end 
    
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
    MaskP(:,:,i) = MaskPoints;
    Images(:,:,i) =  Itex;

    figure(81), 
    g.CData = Itex;
    title(['Imagen ',num2str(i)])
    hold on
    pause();
    Mask(:,:,i) = g1.createMask;

    %Mask(:,:,i) = MaskPoints;

    figure(80),imagesc(Fx_aux.*Mask(:,:,i)), title('Unwrapped H Phase - GrayCode');
    title(['Imagen ',num2str(i)])
    drawnow
end
%% Fit the phase maps to a phase surface phi(u,v)

Mask([1:15 end-15:end],:,:) = 0;
Mask(:,[1:15 end-15:end],:) = 0;

% [Fxa ,Fya ,Maskx ,Masky ] = CleanPhase(Fx(:,:,1), Fy(:,:,1),Mask(:,:,1)>0,1);
[Fxa ,Fya ,Maskx ,Masky ] = CleanPhase(Fx, Fy,Mask>0,1); %  5th order 2D-polynomial
Indi = NaN.*Maskx; Indi(Maskx>0) = 1;

% [Dz5th,FX] =  PhaseAdj5(coefz_if(:,:,:),Maskis,5,1,[],5);

% [mat_int] = Adj2D_5thPol(worldPoints(:,1),M(:,1,1,1),M(:,2,1,1),1:1600,1:1200);

Maps  = RegWcordtoImage(M,worldPoints,[size(Fxa,1) size(Fxa,2)]);

% [U,V] = meshgrid(1:1200,1:1024);
% a = -0.1; b = -0.7; c = 400; d = -0.2; e = -0.3;
%  PhasePrueb = (c+d*U+e*V)./(1+a*U+b*V);
%  
% [Ffaf,Ffr ] = Fracfit2D_1(Fx(:,:,1),Mask(:,:,1)>0); % 
% 
% [Ffaf,Ffr ] = Fracfit2D_1(Fy,Mask>0); % 


%%
save([Direc,carp,carp(1:end-1),'_PhasesData.mat'],'Fx','Fy','Fxa','Fya','M','Indi','Mask','Maps','MaskP','Images')

disp(" Finalizado ")


%% Calibration using Matlab Toolbox - Cam and proj independly

ve =  1:7 ;

% n_poses = 20;
worldPoints = generateCircleGridPoints(patternSize,centerDistance,'PatternType', Pattern_type);
%  worldPoints = (worldPoints/15).*[15.0588 14.9090];
%  worldPoints = (worldPoints).*[250.5/250 199.3/200];

NRcoefc = 2; SkewFlag = 0;
[CamCalib,imagesUsed,estimationErrors] = estimateCameraParameters(M(:,:,ve,1),worldPoints,'EstimateSkew',logical(SkewFlag),'NumRadialDistortionCoefficients',NRcoefc,'EstimateTangentialDistortion',true);

NRcoef = 2; SkewFlag = 0; 
[ProjCalib,imagesUsed,estimationErrors] = estimateCameraParameters(M(:,:,ve,2),worldPoints,'EstimateSkew',logical(SkewFlag),'NumRadialDistortionCoefficients',NRcoef,'EstimateTangentialDistortion',true);


[StereoParams,pairsUsed,estimationErrors] = estimateStereoBaseline(M(:,:,ve,:),worldPoints,CamCalib,ProjCalib) ;


save([Direc,carp,carp(1:end-1),'_TSC_',num2str(SkewFlag),'_',num2str(NRcoefc),'.mat'],'StereoParams')


%% Estereo Calibration using Matlab Toolbox

ve = 1:7;

NRcoef = 2;
SkewFlag = 0;
 worldPoints = generateCircleGridPoints(patternSize,centerDistance,'PatternType', Pattern_type);
%  worldPoints = (worldPoints/15).*[15.0588 14.9090];
[StereoParams,imagesUsed,estimationErrors] = estimateCameraParameters(M(:,:,ve,:),worldPoints,'EstimateSkew',logical(SkewFlag),'NumRadialDistortionCoefficients',NRcoef);
figure, showReprojectionErrors(StereoParams);

% [cameraParams,imagesUsed,estimationErrors] = estimateCameraParameters(shiftdim(M(:,:,:,1)),worldPoints);
% [ProjParams,imagesUsed,estimationErrors] = estimateCameraParameters(shiftdim(M(:,:,:,2)),worldPoints);

% Save Data
save([Direc,carp,carp(1:end-1),'_TSC_',num2str(SkewFlag),'_',num2str(NRcoef),'_J.mat'],'StereoParams')


%% Estereo Calibration by Bouget Toolbox
ve = [1:8 10:19] ;
dire = [Direc,carp];
worldPoints = generateCircleGridPoints(patternSize,centerDistance,'PatternType', Pattern_type);
% worldPoints = (worldPoints/15).*[15.0588 14.9090];
save_calibraciones(dire,M(:,:,ve,1),double(M(:,:,ve,2)),worldPoints,0*[[1 1 1 1 1];[1 1 1 1 1]]',[0 0],0)

disp('done')

%%




