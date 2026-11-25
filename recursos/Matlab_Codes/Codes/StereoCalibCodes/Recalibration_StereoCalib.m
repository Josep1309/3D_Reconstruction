pathExp   = '23-03-22 - Pruebas';
pathR3D = 'WhiteBoardExt';

load(['..\Data\',pathExp,'\',pathR3D,'\',pathR3D,'_PhasesData.mat'],'Fx','Fy','MaskC','images')
% MaskC = Mask;
Indi = NaN*MaskC; Indi(MaskC>0) = 1;



%  Sistema Dell - Basler ac1300 System Info
m_imageWidth = 1600;        %1936   %1280 ;     %2048
m_imageHeight = 1200;       %1464   %1024 ;     %1536
m_projectorWidth =  912;    %912    %1280;      %912
m_projectorHeight = 1140;   %1140   %800;       %1140

%% Dividir data

index = [6 7 8 9 10];
Fx = Fx(:,:,index);
Fy = Fy(:,:,index);
Indi = Indi(:,:,index);
MaskC = MaskC(:,:,index);

%%

MaskC([1:15 end-15:end],:,:) = 0;
MaskC(:,[1:15 end-15:end],:) = 0;

% [Fxa ,Fya ,Maskx ,Masky ] = CleanPhase(Fx(:,:,1), Fy(:,:,1),Mask(:,:,1)>0,1);
[Fxa ,Fya ,Maskx ,Masky ] = CleanPhase(Fx, Fy,MaskC>0,1); %  5th order 2D-polynomial
Indi = NaN.*Maskx; Indi(Maskx>0) = 1;



% [Dz5th,FX] =  PhaseAdj5(coefz_if(:,:,:),Maskis,5,1,[],5);

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

%%

FringePitch = 18;
[erms,dist,Dx_ip, Dy_ip, Dz_ip, Dx_rp, Dy_rp, Dz_rp,errDis] = XYZ_R3D_Target(StereoParams,StereoType,Fxa,Fya,FringePitch,Indi>0,'Fy',Indi>0);
%%


worldPoints = [Dx_ip(indi(:)), Dy_ip(indi(:)), Dz_ip(indi(:)) ];
[uc,vc] = meshgrid(1:m_imageHeight,1:m_imageWidth);
uc = repmat(uc,[1 1 size(Dx_ip,3)]);
vc = repmat(vc,[1 1 size(Dx_ip,3)]);
up = 18*Fxa/(2*pi);
vp = 18*Fya/(2*pi);

M = 

NRcoef = 3; SkewFlag = 0;
[CamCalib,imagesUsed,estimationErrors] = estimateCameraParameters(M(:,:,1:n_poses,1),worldPoints,'EstimateSkew',logical(SkewFlag),'NumRadialDistortionCoefficients',NRcoef,'EstimateTangentialDistortion',true);
NRcoef = 2; SkewFlag = 0; 
[ProjCalib,imagesUsed,estimationErrors] = estimateCameraParameters(M(:,:,1:n_poses,2),worldPoints,'EstimateSkew',logical(SkewFlag),'NumRadialDistortionCoefficients',NRcoef,'EstimateTangentialDistortion',true);


[StereoParams,pairsUsed,estimationErrors] = estimateStereoBaseline(M(:,:,1:n_poses,:),worldPoints,CamCalib,ProjCalib) ;
save([Direc,carp,carp(1:end-1),'_TSC_',num2str(SkewFlag),'_',num2str(NRcoef),'.mat'],'StereoParams')


%%























