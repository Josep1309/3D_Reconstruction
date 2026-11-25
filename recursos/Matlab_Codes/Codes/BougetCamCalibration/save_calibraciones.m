function save_calibraciones(dire,cP,pP,wP,dc,Skew,recal_params)
% Calcula los parametros estereos del sistema de proyeccion de franjas
% cP : Camera Points
% pP : Projector Points
% wP : World Points
% dc : Distortion coefficients enabler dc = [[kc1 kc2 pc1 pc2 kc3]' [kp1 kp2 pp1 pp2 kp3]']
% Skew: Skew enabler Skew = [Skewc Skewp]; 
% recal_params: Recalculate parameters in stereo calibration 1 or 0

%%
%
% tic
fecha = dire;
mkdir(fecha)
vc = strrep(num2str(dc(:,1)'),' ','');
vp = strrep(num2str(dc(:,2)'),' ','');
ss = strrep(num2str(Skew),' ','');
name_cam = [fecha, 'Cam_', vc,'_',num2str(Skew(1))];
name_pro = [fecha, 'Pro_', vp,'_',num2str(Skew(2))];
name_ste = [fecha,'Ste_R',num2str(recal_params),'C',vc,'P',vp,'S',ss];
% toc

if(exist([name_cam,'.mat'],'file')~=2)
    Cal_cam([wP,wP(:,1).*0],cP,name_cam,dc(:,1),Skew(1),[1600 1200],[1600 1200]/2);
%     Cal_cam([wP,wP(:,1).*0],cP,name_cam,dc(:,1),Skew(1),[1600 1200]);
end

name_pro
if(exist([name_pro,'.mat'],'file')~=2)
% Cal_cam([wP,wP(:,1).*0],pP,name_pro,dc(:,2),Skew(2),[1280 800]);
Cal_cam([wP,wP(:,1).*0],pP,name_pro,dc(:,2),Skew(2),[793 1140*2],[793/2 1140*2]);
end

if(exist([name_ste,'.mat'],'file')~=2)
Cal_stereo([name_cam '.mat'],[name_pro '.mat'],name_ste,recal_params);
end

end



%go_calib_optim_iter
%
%Main calibration function. Computes the intrinsic andextrinsic parameters.
%Runs as a script.
%
%INPUT: x_1,x_2,x_3,...: Feature locations on the images
%       X_1,X_2,X_3,...: Corresponding grid coordinates
%
%OUTPUT: fc: Camera focal length
%        cc: Principal point coordinates
%        alpha_c: Skew coefficient
%        kc: Distortion coefficients
%        KK: The camera matrix (containing fc and cc)
%        omc_1,omc_2,omc_3,...: 3D rotation vectors attached to the grid positions in space
%        Tc_1,Tc_2,Tc_3,...: 3D translation vectors attached to the grid positions in space
%        Rc_1,Rc_2,Rc_3,...: 3D rotation matrices corresponding to the omc vectors
%
%Method: Minimizes the pixel reprojection error in the least squares sense over the intrinsic
%        camera parameters, and the extrinsic parameters (3D locations of the grids in space)
%
%Note: If the intrinsic camera parameters (fc, cc, kc) do not exist before, they are initialized through
%      the function init_intrinsic_param.m. Otherwise, the variables in memory are used as initial guesses.
%
%Note: The row vector active_images consists of zeros and ones. To deactivate an image, set the
%      corresponding entry in the active_images vector to zero.
%
%VERY IMPORTANT: This function works for 2D and 3D calibration rigs, except for init_intrinsic_param.m
%that is so far implemented to work only with 2D rigs.
%In the future, a more general function will be there.
%For now, if using a 3D calibration rig, quick_init is set to 1 for an easy initialization of the focal length
function [KK,Tc,Rc,Re]=Cal_cam(X1,x1,Name,est_dist,est_alpha,n,cc)

% center_optim = 0;
if(nargin>4)
    nx = n(1);
    ny = n(2);
end

n_ima = size(x1,3);
ind_active = 1:n_ima;
active_images = 1:n_ima;

for kk = 1:n_ima
    eval(['X_' num2str(kk) '= X1'';']);
    eval(['x_' num2str(kk) '= x1(:,:,' num2str(kk) ')'';']);
end



if ~exist('desactivated_images'),
    desactivated_images = [];
end;



if ~exist('est_aspect_ratio'),
    est_aspect_ratio = 1;
end;

if ~exist('est_fc');
    est_fc = [1;1]; % Set to zero if you do not want to estimate the focal length (it may be useful! believe it or not!)
end;

if ~exist('recompute_extrinsic'),
    recompute_extrinsic = 1; % Set this variable to 0 in case you do not want to recompute the extrinsic parameters
    % at each iterstion.
end;

if ~exist('MaxIter'),
    MaxIter = 60; % Maximum number of iterations in the gradient descent
end;

if ~exist('check_cond'),
    check_cond = 1; % Set this variable to 0 in case you don't want to extract view dynamically
end;

if ~exist('center_optim'),
    center_optim = 1; %%% Set this variable to 0 if your do not want to estimate the principal point
end;

if exist('est_dist'),
    if length(est_dist) == 4,
        est_dist = [est_dist ; 0];
    end;
end;

if ~exist('est_dist'),
    est_dist = [0;0;0;0;0];
%     est_dist = [1;1;1;1;1];
end;
if ~exist('est_alpha'),
    est_alpha = 0; % by default, do not estimate skew
end;


% Little fix in case of stupid values in the binary variables:
center_optim = double(~~center_optim);
est_alpha = double(~~est_alpha);
est_dist = double(~~est_dist);
est_fc = double(~~est_fc);
est_aspect_ratio = double(~~est_aspect_ratio);



fprintf(1,'\n');

if ~exist('nx')&~exist('ny'),
    fprintf(1,'WARNING: No image size (nx,ny) available. Setting nx=640 and ny=480. If these are not the right values, change values manually.\n');
    nx = 1280;
    ny = 1024;
end;


% check_active_images;


quick_init = 0; % Set to 1 for using a quick init (necessary when using 3D rigs)


% Check 3D-ness of the calibration rig:
 rig3D = 0;
% for kk = ind_active,
%     eval(['X_kk = X_' num2str(kk) ';']);
%     if is3D(X_kk),
%         rig3D = 1;
%     end;
% end;


if center_optim & (length(ind_active) < 2) & ~rig3D,
    fprintf(1,'WARNING: Principal point rejected from the optimization when using one image and planar rig (center_optim = 1).\n');
    center_optim = 0; %%% when using a single image, please, no principal point estimation!!!
    est_alpha = 0;
end;

if ~exist('dont_ask'),
    dont_ask = 0;
end;

if center_optim & (length(ind_active) < 5) & ~rig3D,
    fprintf(1,'WARNING: The principal point estimation may be unreliable (using less than 5 images for calibration).\n');
    %if ~dont_ask,
    %   quest = input('Are you sure you want to keep the principal point in the optimization process? ([]=yes, other=no) ');
    %   center_optim = isempty(quest);
    %end;
end;


% A quick fix for solving conflict
if ~isequal(est_fc,[1;1]),
    est_aspect_ratio=1;
end;
if ~est_aspect_ratio,
    est_fc=[1;1];
end;


if ~est_aspect_ratio,
    fprintf(1,'Aspect ratio not optimized (est_aspect_ratio = 0) -> fc(1)=fc(2). Set est_aspect_ratio to 1 for estimating aspect ratio.\n');
else
    if isequal(est_fc,[1;1]),
        fprintf(1,'Aspect ratio optimized (est_aspect_ratio = 1) -> both components of fc are estimated (DEFAULT).\n');
    end;
end;

if ~isequal(est_fc,[1;1]),
    if isequal(est_fc,[1;0]),
        fprintf(1,'The first component of focal (fc(1)) is estimated, but not the second one (est_fc=[1;0])\n');
    else
        if isequal(est_fc,[0;1]),
            fprintf(1,'The second component of focal (fc(1)) is estimated, but not the first one (est_fc=[0;1])\n');
        else
            fprintf(1,'The focal vector fc is not optimized (est_fc=[0;0])\n');
        end;
    end;
end;


if ~center_optim, % In the case where the principal point is not estimated, keep it at the center of the image
    fprintf(1,'Principal point not optimized (center_optim=0). ');
    if ~exist('cc'),
        fprintf(1,'It is kept at the center of the image.\n');
        cc = [(nx-1)/2;(ny-1)/2];
    else
        fprintf(1,'Note: to set it in the middle of the image, clear variable cc, and run calibration again.\n');
    end;
else
    fprintf(1,'Principal point optimized (center_optim=1) - (DEFAULT). To reject principal point, set center_optim=0\n');
end;


if ~center_optim & (est_alpha),
    fprintf(1,'WARNING: Since there is no principal point estimation (center_optim=0), no skew estimation (est_alpha = 0)\n');
    est_alpha = 0;  
end;

if ~est_alpha,
    fprintf(1,'Skew not optimized (est_alpha=0) - (DEFAULT)\n');
    alpha_c = 0;
else
    fprintf(1,'Skew optimized (est_alpha=1). To disable skew estimation, set est_alpha=0.\n');
end;


if ~prod(double(est_dist)),
    fprintf(1,'Distortion not fully estimated (defined by the variable est_dist):\n');
    if ~est_dist(1),
        fprintf(1,'     Second order distortion not estimated (est_dist(1)=0).\n');
    end;
    if ~est_dist(2),
        fprintf(1,'     Fourth order distortion not estimated (est_dist(2)=0).\n');
    end;
    if ~est_dist(5),
        fprintf(1,'     Sixth order distortion not estimated (est_dist(5)=0) - (DEFAULT) .\n');
    end;
    if ~prod(double(est_dist(3:4))),
        fprintf(1,'     Tangential distortion not estimated (est_dist(3:4)~=[1;1]).\n');
    end;
end;

% Check 3D-ness of the calibration rig:
 rig3D = 0;
% for kk = ind_active,
%     eval(['X_kk = X_' num2str(kk) ';']);
%     if is3D(X_kk),
%         rig3D = 1;
%     end;
% end;

% If the rig is 3D, then no choice: the only valid initialization is manual!
if rig3D,
    quick_init = 1;
end;



alpha_smooth = 0.4; % set alpha_smooth = 1; for steepest gradient descent


% Conditioning threshold for view rejection
thresh_cond = 1e6;



%% Initialization of the intrinsic parameters (if necessary)

if ~exist('cc','var'),
    fprintf(1,'Initialization of the principal point at the center of the image.\n');
    cc = [(nx-1)/2;(ny-1)];
    alpha_smooth = 0.4; % slow convergence
end;


if exist('kc','var'),
    if length(kc) == 4;
        fprintf(1,'Adding a new distortion coefficient to kc -> radial distortion model up to the 6th degree');
        kc = [kc;0];
    end;
end;



if ~exist('alpha_c','var'),
    fprintf(1,'Initialization of the image skew to zero.\n');
    alpha_c = 0;
    alpha_smooth = 0.4; % slow convergence
end;

if ~exist('fc','var')& quick_init,
    FOV_angle = 35; % Initial camera field of view in degrees
    fprintf(1,['Initialization of the focal length to a FOV of ' num2str(FOV_angle) ' degrees.\n']);
    fc = (nx/2)/tan(pi*FOV_angle/360) * ones(2,1);
    est_fc = [1;1];
    alpha_smooth = 0.4; % slow 
end;



if ~exist('fc','var'),
    % Initialization of the intrinsic parameters:
    fprintf(1,'Initialization of the intrinsic parameters using the vanishing points of planar patterns.\n')
    init_intrinsic_param; % The right way to go (if quick_init is not active)!
    alpha_smooth = 0.4; % slow convergence
    est_fc = [1;1];
end;


if ~exist('kc','var'),
    fprintf(1,'Initialization of the image distortion to zero.\n');
    kc = zeros(5,1);
    alpha_smooth = 0.4; % slow convergence
end;

if ~est_aspect_ratio,
    fc(1) = (fc(1)+fc(2))/2;
    fc(2) = fc(1);
end;

if ~prod(double(est_dist)),
    % If no distortion estimated, set to zero the variables that are not estimated
    kc = kc .* est_dist;
end;


if ~prod(double(est_fc)),
    fprintf(1,'Warning: The focal length is not fully estimated (est_fc ~= [1;1])\n');
end;


%%% Initialization of the extrinsic parameters for global minimization:
comp_ext_calib;



%%% Initialization of the global parameter vector:
% cc = [400 1100]';
init_param = [fc;cc;alpha_c;kc;zeros(5,1)]; 

for kk = 1:n_ima,
    eval(['omckk = omc_' num2str(kk) ';']);
    eval(['Tckk = Tc_' num2str(kk) ';']);
    init_param = [init_param; omckk ; Tckk];    
end;



%-------------------- Main Optimization:

fprintf(1,'\nMain calibration optimization procedure - Number of images: %d\n',length(ind_active));


param = init_param;
change = 1;

iter = 0;

fprintf(1,'Gradient descent iterations: ');

param_list = param;


while (change > 1e-9)&(iter < MaxIter),
    
    fprintf(1,'%d...',iter+1);
    
    % To speed up: pre-allocate the memory for the Jacobian JJ3.
    % For that, need to compute the total number of points.
    
    %% The first step consists of updating the whole vector of knowns (intrinsic + extrinsic of active
    %% images) through a one step steepest gradient descent.
    
    
    f = param(1:2);
    c = param(3:4);
    alpha = param(5);
    k = param(6:10);
    
    
    % Compute the size of the Jacobian matrix:
    N_points_views_active = N_points_views(ind_active);
    
    JJ3 = sparse([],[],[],15 + 6*n_ima,15 + 6*n_ima,126*n_ima + 225);
    ex3 = zeros(15 + 6*n_ima,1);
    
    
    for kk = ind_active, %1:n_ima,
        %if active_images(kk),
        
        omckk = param(15+6*(kk-1) + 1:15+6*(kk-1) + 3); 
        
        Tckk = param(15+6*(kk-1) + 4:15+6*(kk-1) + 6); 
        
        if isnan(omckk(1)),
            fprintf(1,'Intrinsic parameters at frame %d do not exist\n',kk);
            return;
        end;
        
%         X_kk = X1';
        eval(['X_kk = X_' num2str(kk) ';']);
%         x_kk = x1(:,:,kk)';
        eval(['x_kk = x_' num2str(kk) ';']);
        
        Np = N_points_views(kk);
        
        if ~est_aspect_ratio,
            [x,dxdom,dxdT,dxdf,dxdc,dxdk,dxdalpha] = project_points2(X_kk,omckk,Tckk,f(1),c,k,alpha);
            dxdf = repmat(dxdf,[1 2]);
        else
            [x,dxdom,dxdT,dxdf,dxdc,dxdk,dxdalpha] = project_points2(X_kk,omckk,Tckk,f,c,k,alpha);
        end;
        
        exkk = x_kk - x;
        
        A = [dxdf dxdc dxdalpha dxdk]';
        B = [dxdom dxdT]';
        
        JJ3(1:10,1:10) = JJ3(1:10,1:10) + sparse(A*A');
        JJ3(15+6*(kk-1) + 1:15+6*(kk-1) + 6,15+6*(kk-1) + 1:15+6*(kk-1) + 6) = sparse(B*B');
        
        AB = sparse(A*B');
        JJ3(1:10,15+6*(kk-1) + 1:15+6*(kk-1) + 6) = AB;
        JJ3(15+6*(kk-1) + 1:15+6*(kk-1) + 6,1:10) = (AB)';
        
        ex3(1:10) = ex3(1:10) + A*exkk(:);
        ex3(15+6*(kk-1) + 1:15+6*(kk-1) + 6) = B*exkk(:);
        
        % Check if this view is ill-conditioned:
        if check_cond,
            JJ_kk = B'; %[dxdom dxdT];
            if (cond(JJ_kk)> thresh_cond),
                active_images(kk) = 0;
                fprintf(1,'\nWarning: View #%d ill-conditioned. This image is now set inactive. (note: to disactivate this option, set check_cond=0)\n',kk)
                desactivated_images = [desactivated_images kk];
                param(15+6*(kk-1) + 1:15+6*(kk-1) + 6) = NaN*ones(6,1); 
            end;
        end;
        
        %end;
        
    end;
    
    
    % List of active images (necessary if changed):
%     check_active_images;
    
    
    % The following vector helps to select the variables to update (for only active images):
    selected_variables = [est_fc;center_optim*ones(2,1);est_alpha;est_dist;zeros(5,1);reshape(ones(6,1)*active_images,6*n_ima,1)];
    if ~est_aspect_ratio,
        if isequal(est_fc,[1;1]) | isequal(est_fc,[1;0]),
            selected_variables(2) = 0;
        end;
    end;
    ind_Jac = find(selected_variables)';
    
    JJ3 = JJ3(ind_Jac,ind_Jac);
    ex3 = ex3(ind_Jac);
    
    JJ2_inv = inv(JJ3); % not bad for sparse matrices!!
    
    
    % Smoothing coefficient:
    
    alpha_smooth2 = 1-(1-alpha_smooth)^(iter+1); %set to 1 to undo any smoothing!
    
    param_innov = alpha_smooth2*JJ2_inv*ex3;
    
    
    param_up = param(ind_Jac) + param_innov;
    param(ind_Jac) = param_up;
    
    
    % New intrinsic parameters:
    
    fc_current = param(1:2);
    cc_current = param(3:4);

    if center_optim & ((param(3)<0)|(param(3)>nx)|(param(4)<0)|(param(4)>ny)),
        fprintf(1,'Warning: it appears that the principal point cannot be estimated. Setting center_optim = 0\n');
        center_optim = 0;
        cc_current = c;
    else
        cc_current = param(3:4);
    end;
    
    alpha_current = param(5);
    kc_current = param(6:10);
    
    if ~est_aspect_ratio & isequal(est_fc,[1;1]),
        fc_current(2) = fc_current(1);
        param(2) = param(1);
    end;
    
    % Change on the intrinsic parameters:
    change = norm([fc_current;cc_current] - [f;c])/norm([fc_current;cc_current]);
    
    
    %% Second step: (optional) - It makes convergence faster, and the region of convergence LARGER!!!
    %% Recompute the extrinsic parameters only using compute_extrinsic.m (this may be useful sometimes)
    %% The complete gradient descent method is useful to precisely update the intrinsic parameters.
    
    
    if recompute_extrinsic,
        MaxIter2 = 20;
        for kk =1:n_ima,
            %if active_images(kk),
            omc_current = param(15+6*(kk-1) + 1:15+6*(kk-1) + 3);
            Tc_current = param(15+6*(kk-1) + 4:15+6*(kk-1) + 6);
            eval(['x_kk = x_' num2str(kk) ';']);
            eval(['X_kk = X_' num2str(kk) ';']);
            [omc_current,Tc_current] = compute_extrinsic_init(x_kk,X_kk,fc_current,cc_current,kc_current,alpha_current);
            [omckk,Tckk,Rckk,JJ_kk] = compute_extrinsic_refine(omc_current,Tc_current,x_kk,X_kk,fc_current,cc_current,kc_current,alpha_current,MaxIter2,thresh_cond);
            if check_cond,
                if (cond(JJ_kk)> thresh_cond),
                    active_images(kk) = 0;
                    fprintf(1,'\nWarning: View #%d ill-conditioned. This image is now set inactive. (note: to disactivate this option, set check_cond=0)\n',kk);
                    desactivated_images = [desactivated_images kk];
                    omckk = NaN*ones(3,1);
                    Tckk = NaN*ones(3,1);
                end;
            end;
            param(15+6*(kk-1) + 1:15+6*(kk-1) + 3) = omckk;
            param(15+6*(kk-1) + 4:15+6*(kk-1) + 6) = Tckk;
            %end;
        end;
    end;
    
    param_list = [param_list param];
    iter = iter + 1;
    
end;

fprintf(1,'done\n');



%%%--------------------------- Computation of the error of estimation:

fprintf(1,'Estimation of uncertainties...');


% check_active_images;

solution = param;


% Extraction of the paramters for computing the right reprojection error:

fc = solution(1:2);
cc = solution(3:4);
alpha_c = solution(5);
kc = solution(6:10);

for kk = 1:n_ima,
    
    if active_images(kk), 
        
        omckk = solution(15+6*(kk-1) + 1:15+6*(kk-1) + 3);%***   
        Tckk = solution(15+6*(kk-1) + 4:15+6*(kk-1) + 6);%*** 
        Rckk = rodrigues(omckk);
        
    else
        
        omckk = NaN*ones(3,1);   
        Tckk = NaN*ones(3,1);
        Rckk = NaN*ones(3,3);
        
    end;
    
    
    Rc_(:,:,kk) = Rckk;
    Tc_(:,kk) = Tckk;
    eval(['omc_' num2str(kk) ' = omckk;']);
    eval(['Rc_' num2str(kk) ' = Rckk;']);
    eval(['Tc_' num2str(kk) ' = Tckk;']);
    
end;


% Recompute the error (in the vector ex):
comp_error_calib;

sigma_x = std(ex(:));

% Compute the size of the Jacobian matrix:
N_points_views_active = N_points_views(ind_active);

JJ3 = sparse([],[],[],15 + 6*n_ima,15 + 6*n_ima,126*n_ima + 225);

for kk = ind_active,
    
    omckk = param(15+6*(kk-1) + 1:15+6*(kk-1) + 3); 
    Tckk = param(15+6*(kk-1) + 4:15+6*(kk-1) + 6); 
    
    eval(['X_kk = X_' num2str(kk) ';']);
%     X_kk = X(:,:,kk)';
    
    Np = N_points_views(kk);
    
    %[x,dxdom,dxdT,dxdf,dxdc,dxdk,dxdalpha] = project_points2(X_kk,omckk,Tckk,fc,cc,kc,alpha_c);
    
    if ~est_aspect_ratio,
        [x,dxdom,dxdT,dxdf,dxdc,dxdk,dxdalpha] = project_points2(X_kk,omckk,Tckk,fc(1),cc,kc,alpha_c);
        dxdf = repmat(dxdf,[1 2]);
    else
        [x,dxdom,dxdT,dxdf,dxdc,dxdk,dxdalpha] = project_points2(X_kk,omckk,Tckk,fc,cc,kc,alpha_c);
    end;
    
    A = [dxdf dxdc dxdalpha dxdk]';
    B = [dxdom dxdT]';
    
    JJ3(1:10,1:10) = JJ3(1:10,1:10) + sparse(A*A');
    JJ3(15+6*(kk-1) + 1:15+6*(kk-1) + 6,15+6*(kk-1) + 1:15+6*(kk-1) + 6) = sparse(B*B');
    
    AB = sparse(A*B');
    JJ3(1:10,15+6*(kk-1) + 1:15+6*(kk-1) + 6) = AB;
    JJ3(15+6*(kk-1) + 1:15+6*(kk-1) + 6,1:10) = (AB)';
    
end;

JJ3 = JJ3(ind_Jac,ind_Jac);

JJ2_inv = inv(JJ3); % not bad for sparse matrices!!

param_error = zeros(6*n_ima+15,1);
param_error(ind_Jac) =  3*sqrt(full(diag(JJ2_inv)))*sigma_x;

solution_error = param_error;

if ~est_aspect_ratio & isequal(est_fc,[1;1]),
    solution_error(2) = solution_error(1);
end;


%%% Extraction of the final intrinsic and extrinsic paramaters:

extract_parameters;

fprintf(1,'done\n');


fprintf(1,'\n\nCalibration results after optimization (with uncertainties):\n\n');
fprintf(1,'Focal Length:          fc = [ %3.5f   %3.5f ] ± [ %3.5f   %3.5f ]\n',[fc;fc_error]);
fprintf(1,'Principal point:       cc = [ %3.5f   %3.5f ] ± [ %3.5f   %3.5f ]\n',[cc;cc_error]);
fprintf(1,'Skew:             alpha_c = [ %3.5f ] ± [ %3.5f  ]   => angle of pixel axes = %3.5f ± %3.5f degrees\n',[alpha_c;alpha_c_error],90 - atan(alpha_c)*180/pi,atan(alpha_c_error)*180/pi);
fprintf(1,'Distortion:            kc = [ %3.5f   %3.5f   %3.5f   %3.5f  %5.5f ] ± [ %3.5f   %3.5f   %3.5f   %3.5f  %5.5f ]\n',[kc;kc_error]);   
fprintf(1,'Pixel error:          err = [ %3.5f   %3.5f ]\n\n',err_std); 
fprintf(1,'Note: The numerical errors are approximately three times the standard deviations (for reference).\n\n\n')
%fprintf(1,'      For accurate (and stable) error estimates, it is recommended to run Calibration once again.\n\n\n')



%%% Some recommendations to the user to reject some of the difficult unkowns... Still in debug mode.

alpha_c_min = alpha_c - alpha_c_error/2;
alpha_c_max = alpha_c + alpha_c_error/2;

if (alpha_c_min < 0) & (alpha_c_max > 0),
    fprintf(1,'Recommendation: The skew coefficient alpha_c is found to be equal to zero (within its uncertainty).\n');
    fprintf(1,'                You may want to reject it from the optimization by setting est_alpha=0 and run Calibration\n\n');
end;

kc_min = kc - kc_error/2;
kc_max = kc + kc_error/2;

prob_kc = (kc_min < 0) & (kc_max > 0);

if ~(prob_kc(3) & prob_kc(4))
    prob_kc(3:4) = [0;0];
end;


if sum(prob_kc),
    fprintf(1,'Recommendation: Some distortion coefficients are found equal to zero (within their uncertainties).\n');
    fprintf(1,'                To reject them from the optimization set est_dist=[%d;%d;%d;%d;%d] and run Calibration\n\n',est_dist & ~prob_kc);
end;

% ext_calib
reproject_calib
% nx=1280; ny=800;
visualize_distortions
saving_calib
end


function S = Cal_stereo(nomL,nomR,Name,recompute)
% dir('*mat');

% fprintf(1,'Loading of the individual left and right camera calibration files\n');

% calib_file_name_left = input('Name of the left camera calibration file ([]=Calib_Results_left.mat): ','s');
calib_file_name_left = nomL;
% if isempty(calib_file_name_left),
%     calib_file_name_left = 'Calib_Results_left.mat';
% end;
 recompute_intrinsic_right =recompute;
 recompute_intrinsic_left =recompute;
% calib_file_name_right = input('Name of the right camera calibration file ([]=Calib_Results_right.mat): ','s');
calib_file_name_right = nomR;
% if isempty(calib_file_name_right),
%     calib_file_name_right = 'Calib_Results_right.mat';
% end;


if (exist(calib_file_name_left)~=2)|(exist(calib_file_name_right)~=2),
    fprintf(1,'Error: left and right calibration files do not exist.\n');
    return;
end;


fprintf(1,'Loading the left camera calibration result file %s...\n',calib_file_name_left);

clear calib_name

load(calib_file_name_left);

fc_left = fc;
cc_left = cc;
kc_left = kc;
alpha_c_left = alpha_c;
fc_left_error = fc_error;
cc_left_error = cc_error;
kc_left_error = kc_error;
alpha_c_left_error = alpha_c_error;
KK_left = KK;

if exist('calib_name'),
    calib_name_left = calib_name;
    format_image_left = format_image;
    type_numbering_left = type_numbering;
    image_numbers_left = image_numbers;
    N_slots_left = N_slots;
else
    calib_name_left = '';
    format_image_left = '';
    type_numbering_left = '';
    image_numbers_left = '';
    N_slots_left = '';
end;

    
X_left = [];


om_left_list = [];
T_left_list = [];

for kk = 1:n_ima,
   
   if active_images(kk),
      
      eval(['Xkk = X_' num2str(kk) ';']);
      eval(['omckk = omc_' num2str(kk) ';']);
      eval(['Rckk = Rc_' num2str(kk) ';']);
      eval(['Tckk = Tc_' num2str(kk) ';']);
      
      N = size(Xkk,2);
      
      Xckk = Rckk * Xkk  + Tckk*ones(1,N);
      
      X_left = [X_left Xckk];

      om_left_list = [om_left_list omckk];
      
      T_left_list = [T_left_list Tckk];
      
  end;
end;



fprintf(1,'Loading the right camera calibration result file %s...\n',calib_file_name_right);

clear calib_name

load(calib_file_name_right);

fc_right = fc;
cc_right = cc;
kc_right = kc;
alpha_c_right = alpha_c;
KK_right = KK;
fc_right_error = fc_error;
cc_right_error = cc_error;
kc_right_error = kc_error;
alpha_c_right_error = alpha_c_error;

if exist('calib_name'),
    calib_name_right = calib_name;
    format_image_right = format_image;
    type_numbering_right = type_numbering;
    image_numbers_right = image_numbers;
    N_slots_right = N_slots;
else
    calib_name_right = '';
    format_image_right = '';
    type_numbering_right = '';
    image_numbers_right = '';
    N_slots_right = '';
end;

X_right = [];

om_right_list = [];
T_right_list = [];


for kk = 1:n_ima,
   
   if active_images(kk),
      
      eval(['Xkk = X_' num2str(kk) ';']);
      eval(['omckk = omc_' num2str(kk) ';']);
      eval(['Rckk = Rc_' num2str(kk) ';']);
      eval(['Tckk = Tc_' num2str(kk) ';']);
      
      N = size(Xkk,2);
      
      Xckk = Rckk * Xkk  + Tckk*ones(1,N);
      
      X_right = [X_right Xckk];
      
      om_right_list = [om_right_list omckk];
      T_right_list = [T_right_list Tckk];
      
   end;
end;




om_ref_list = [];
T_ref_list = [];
for ii = 1:size(om_left_list,2),
    % Align the structure from the first view:
    R_ref = rodrigues(om_right_list(:,ii)) * rodrigues(om_left_list(:,ii))';
    T_ref = T_right_list(:,ii) - R_ref * T_left_list(:,ii);
    om_ref = rodrigues(R_ref);
    om_ref_list = [om_ref_list om_ref];
    T_ref_list = [T_ref_list T_ref];
end;


% Robust estimate of the initial value for rotation and translation between the two views:
om = median(om_ref_list,2);
T = median(T_ref_list,2);




if 0,
    figure(10);
    plot3(X_right(1,:),X_right(2,:),X_right(3,:),'bo');
    hold on;
    [Xr2] = rigid_motion(X_left,om,T);
    plot3(Xr2(1,:),Xr2(2,:),Xr2(3,:),'r+');
    hold off;
    drawnow;
end;


R = rodrigues(om);



% Re-optimize now over all the set of extrinsic unknows (global optimization) and intrinsic parameters:

load(calib_file_name_left); % Calib_Results_left;

for kk = 1:n_ima,
   if active_images(kk),
      eval(['X_left_'  num2str(kk) ' = X_' num2str(kk) ';']);
      eval(['x_left_'  num2str(kk) ' = x_' num2str(kk) ';']);
      eval(['omc_left_' num2str(kk) ' = omc_' num2str(kk) ';']);
      eval(['Rc_left_' num2str(kk) ' = Rc_' num2str(kk) ';']);
      eval(['Tc_left_' num2str(kk) ' = Tc_' num2str(kk) ';']);
   end;
end;

center_optim_left = center_optim;
est_alpha_left = est_alpha;
est_dist_left = est_dist;
est_fc_left = est_fc;
est_aspect_ratio_left = est_aspect_ratio;
active_images_left = active_images;


load(calib_file_name_right);

for kk = 1:n_ima,
   if active_images(kk),
      eval(['X_right_'  num2str(kk) ' = X_' num2str(kk) ';']);
      eval(['x_right_'  num2str(kk) ' = x_' num2str(kk) ';']);
   end;
end;

center_optim_right = center_optim;
est_alpha_right = est_alpha;
est_dist_right = est_dist;
est_fc_right = est_fc;
est_aspect_ratio_right = est_aspect_ratio;
active_images_right = active_images;


active_images = active_images_left & active_images_right;



fprintf(1,'\n\n\nStereo calibration parameters after loading the individual calibration files:\n');


fprintf(1,'\n\nIntrinsic parameters of left camera:\n\n');
fprintf(1,'Focal Length:          fc_left = [ %3.5f   %3.5f ] ± [ %3.5f   %3.5f ]\n',[fc_left;fc_left_error]);
fprintf(1,'Principal point:       cc_left = [ %3.5f   %3.5f ] ± [ %3.5f   %3.5f ]\n',[cc_left;cc_left_error]);
fprintf(1,'Skew:             alpha_c_left = [ %3.5f ] ± [ %3.5f  ]   => angle of pixel axes = %3.5f ± %3.5f degrees\n',[alpha_c_left;alpha_c_left_error],90 - atan(alpha_c_left)*180/pi,atan(alpha_c_left_error)*180/pi);
fprintf(1,'Distortion:            kc_left = [ %3.5f   %3.5f   %3.5f   %3.5f  %5.5f ] ± [ %3.5f   %3.5f   %3.5f   %3.5f  %5.5f ]\n',[kc_left;kc_left_error]);   


fprintf(1,'\n\nIntrinsic parameters of right camera:\n\n');
fprintf(1,'Focal Length:          fc_right = [ %3.5f   %3.5f ] ± [ %3.5f   %3.5f ]\n',[fc_right;fc_right_error]);
fprintf(1,'Principal point:       cc_right = [ %3.5f   %3.5f ] ± [ %3.5f   %3.5f ]\n',[cc_right;cc_right_error]);
fprintf(1,'Skew:             alpha_c_right = [ %3.5f ] ± [ %3.5f  ]   => angle of pixel axes = %3.5f ± %3.5f degrees\n',[alpha_c_right;alpha_c_right_error],90 - atan(alpha_c_right)*180/pi,atan(alpha_c_right_error)*180/pi);
fprintf(1,'Distortion:            kc_right = [ %3.5f   %3.5f   %3.5f   %3.5f  %5.5f ] ± [ %3.5f   %3.5f   %3.5f   %3.5f  %5.5f ]\n',[kc_right;kc_right_error]);   


fprintf(1,'\n\nExtrinsic parameters (position of right camera wrt left camera):\n\n');
fprintf(1,'Rotation vector:             om = [ %3.5f   %3.5f  %3.5f ]\n',om);
fprintf(1,'Translation vector:           T = [ %3.5f   %3.5f  %3.5f ]\n',T);


go_calib_stereo


% fprintf(1,['Saving the stereo calibration results in ' Name '.mat...\n']);

string_save = ['save ''' Name ''' om R T alpha_c_right recompute_intrinsic_right recompute_intrinsic_left calib_name_left format_image_left type_numbering_left image_numbers_left N_slots_left calib_name_right format_image_right type_numbering_right image_numbers_right N_slots_right fc_left cc_left kc_left alpha_c_left KK_left fc_right cc_right kc_right alpha_c_right KK_right active_images dX dY nx ny n_ima active_images_right active_images_left inconsistent_images center_optim_left est_alpha_left est_dist_left est_fc_left est_aspect_ratio_left center_optim_right est_alpha_right est_dist_right est_fc_right est_aspect_ratio_right history param param_error sigma_x om_error T_error fc_left_error cc_left_error kc_left_error alpha_c_left_error fc_right_error cc_right_error kc_right_error alpha_c_right_error'];

for kk = 1:n_ima
    if active_images(kk)
        eval(['RotationMatrices(:,:,kk) = rodrigues( omc_left_', num2str(kk),');']);
        eval(['TranslationVectors(:,kk) = Tc_left_', num2str(kk),';'])
    end
end
NumPatterns = n_ima;
string_save = [string_save ' RotationMatrices TranslationVectors NumPatterns'];
eval(string_save);


end
















